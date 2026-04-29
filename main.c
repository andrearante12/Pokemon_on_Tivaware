/*
 * final_project/main.c
 * Streams a pre-rendered Pokemon battle scene over UART then supports
 * targeted partial updates for HP bars, move cursor, dialog text, sprites.
 *
 */

#include <stdint.h>
#include <stdbool.h>
#include "inc/hw_memmap.h"
#include "inc/hw_types.h"
#include "inc/tm4c123gh6pm.h"
#include "driverlib/sysctl.h"
#include "driverlib/uart.h"
#include "driverlib/gpio.h"
#include "driverlib/pin_map.h"
#include "driverlib/adc.h"
#include "driverlib/timer.h"
#include "driverlib/interrupt.h"
#include "scene_data.h"
#include "scene_pos.h"
#include "inc/hw_gpio.h"
#include "music/playlist.h"
#include "sprites.h"

#define E_SPRITE_ROWS  69
#define P_SPRITE_ROWS  74
#define SPRITE_CLEAR_W 140   // spaces per row 

#define F_CPU 40000000UL

// Joystick thresholds (12-bit ADC, center ≈ 2048)
#define JOY_LO   800
#define JOY_HI  3200

// UART init
void UART_initialize(void)
{
    // Clock Programming
    SysCtlClockSet(SYSCTL_SYSDIV_5 | SYSCTL_USE_PLL | SYSCTL_XTAL_16MHZ | SYSCTL_OSC_MAIN);

    // Enable UART and GPIOA
    SysCtlPeripheralEnable(SYSCTL_PERIPH_UART0);
    SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOA);

    // Configure UART Pins
    GPIOPinConfigure(GPIO_PA0_U0RX);
    GPIOPinConfigure(GPIO_PA1_U0TX);
    GPIOPinTypeUART(GPIO_PORTA_BASE, GPIO_PIN_0 | GPIO_PIN_1);

    // Set Baudrate = 115200, 8-N-1
    UARTConfigSetExpClk(UART0_BASE, SysCtlClockGet(), 115200, (UART_CONFIG_WLEN_8 | UART_CONFIG_STOP_ONE | UART_CONFIG_PAR_NONE));
}

// UART helper functions
static void uart_putc(char c)
{
    UARTCharPut(UART0_BASE, c);
}

static void uart_puts(const char *s)
{
    while (*s) uart_putc(*s++);
}

static void uart_putint(int n)
{
    char buf[6];
    int i = 0;
    if (n == 0) { uart_putc('0'); return; }
    while (n > 0) { buf[i++] = (char)('0' + n % 10); n /= 10; }
    while (i-- > 0) uart_putc(buf[i]);
}

// Move cursor to row/col
static void ansi_goto(int row, int col)
{
    uart_puts("\033[");
    uart_putint(row);
    uart_putc(';');
    uart_putint(col);
    uart_putc('H');
}

// ADC + Joystick initialize
void ADC_initialize(void)
{
    SysCtlPeripheralEnable(SYSCTL_PERIPH_ADC0);
    SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOE);
    GPIOPinTypeADC(GPIO_PORTE_BASE, GPIO_PIN_3 | GPIO_PIN_2);
    ADCSequenceConfigure(ADC0_BASE, 3, ADC_TRIGGER_PROCESSOR, 0);
    ADCSequenceStepConfigure(ADC0_BASE, 3, 0,
                             ADC_CTL_CH0 | ADC_CTL_IE | ADC_CTL_END);
    ADCSequenceEnable(ADC0_BASE, 3);

    SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOB);
    GPIOPinTypeGPIOInput(GPIO_PORTB_BASE, GPIO_PIN_0);
    GPIOPadConfigSet(GPIO_PORTB_BASE, GPIO_PIN_0,
                     GPIO_STRENGTH_2MA, GPIO_PIN_TYPE_STD_WPU);

    // SW1 = PF4, SW2 = PF0 (active low)
    SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOF);
    
    // PF0 is NMI-locked, must unlock before configuring
    HWREG(GPIO_PORTF_BASE + GPIO_O_LOCK) = GPIO_LOCK_KEY;
    HWREG(GPIO_PORTF_BASE + GPIO_O_CR)  |= GPIO_PIN_0;
    HWREG(GPIO_PORTF_BASE + GPIO_O_LOCK) = 0;
    GPIOPinTypeGPIOInput(GPIO_PORTF_BASE, GPIO_PIN_4 | GPIO_PIN_0);
    GPIOPadConfigSet(GPIO_PORTF_BASE, GPIO_PIN_4 | GPIO_PIN_0,
                     GPIO_STRENGTH_2MA, GPIO_PIN_TYPE_STD_WPU);
}

// Sample one ADC channel and return the 12-bit result (0..4095).
static uint32_t read_adc_ch(uint32_t ch)
{
    uint32_t val;
    ADCSequenceStepConfigure(ADC0_BASE, 3, 0, ch | ADC_CTL_IE | ADC_CTL_END);

    // Clear any old flags
    ADCIntClear(ADC0_BASE, 3);

    // Start analog to digital conversion
    ADCProcessorTrigger(ADC0_BASE, 3);

    // Wait until the conversion finishes
    while (!ADCIntStatus(ADC0_BASE, 3, false)) {}
    ADCIntClear(ADC0_BASE, 3);

    // Read result 
    ADCSequenceDataGet(ADC0_BASE, 3, &val);
    return val;
}

// Game helpers
typedef enum { STATE_MENU, STATE_MOVE_SELECT, STATE_PLAYER_ATK, STATE_ENEMY_ATK, STATE_WIN, STATE_LOSE } game_state_t;

static int sw2_pressed(void)
{
    if (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_0) == 0) {

        // 20 ms debounce
        SysCtlDelay(SysCtlClockGet() / 150);
        return (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_0) == 0);
    }
    return 0;
}

static int sw1_pressed(void)
{
    if (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0) {

        // 20 ms debounce
        SysCtlDelay(SysCtlClockGet() / 150);
        return (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0);
    }
    return 0;
}

static void delay_sec(int n)
{
    while (n-- > 0)
        SysCtlDelay(SysCtlClockGet() / 3);
}

static const int MOVE_ROW[4] = { MOVE0_ROW, MOVE1_ROW, MOVE2_ROW, MOVE3_ROW };
static const int MOVE_COL[4] = { MOVE0_COL, MOVE1_COL, MOVE2_COL, MOVE3_COL };


// Redraws the 3-row HP bar fill  enemy (is_player=0) or player (is_player=1)
void update_hp_bar(int is_player, int hp, int max_hp)
{
    int row    = is_player ? P_HP_BAR_ROW : E_HP_BAR_ROW;
    int col    = is_player ? P_HP_BAR_COL : E_HP_BAR_COL;
    int filled = (max_hp > 0) ? (BAR_W * hp / max_hp) : 0;
    int empty  = BAR_W - filled;
    int r, i;
    for (r = 0; r < 3; r++) {
        ansi_goto(row + r, col);
        for (i = 0; i < filled; i++) uart_puts(BL_FULL);
        for (i = 0; i < empty;  i++) uart_puts(BL_LIGHT);
    }
}

// Update hp percentage
void update_hp_num(int is_player, int hp, int max_hp)
{
    int row = is_player ? P_HP_NUM_ROW  : E_HP_NUM_ROW;
    int col = is_player ? P_HP_NUM_LEFT : E_HP_NUM_LEFT;
    const char * const *rows = is_player ? P_HP_STRINGS[hp] : E_HP_STRINGS[hp];
    int r;

    for (r = 0; r < BLOCK_ROWS; r++) {
        ansi_goto(row + r, col);
        uart_puts(rows[r]);
    }
    (void)max_hp;  
}

// Moves the cursor from old_sel to new_sel 
void update_move_cursor(int old_sel, int new_sel)
{
    int r;
    for (r = 0; r < BLOCK_ROWS; r++) {
        ansi_goto(MOVE_ROW[old_sel] + r, MOVE_COL[old_sel]);
        uart_puts(CURSOR_EMPTY[r]);
    }
    for (r = 0; r < BLOCK_ROWS; r++) {
        ansi_goto(MOVE_ROW[new_sel] + r, MOVE_COL[new_sel]);
        uart_puts(CURSOR_SEL[r]);
    }
}

// Writes a move-slot label 
static void update_move_label(int slot, const char * const *rows)
{
    int r;
    for (r = 0; r < BLOCK_ROWS; r++) {
        ansi_goto(MOVE_ROW[slot] + r, MOVE_COL[slot]);
        uart_puts(rows[r]);
    }
}

// Label tables for the two menus
static const char * const * const MAIN_LABELS[4] = {
    MLBL_FIGHT, MLBL_BAG, MLBL_POKEMON, MLBL_RUN
};
static const char * const * const MOVE_LABELS[4] = {
    MLBL_WATER_GUN, MLBL_TAIL_WHIP, MLBL_TACKLE, MLBL_GROWL
};

// Writes all 4 labels from a table then draws the cursor at sel.
static void show_menu(const char * const * const labels[4], int sel)
{
    int i, r;
    for (i = 0; i < 4; i++)
        update_move_label(i, labels[i]);
    for (r = 0; r < BLOCK_ROWS; r++) {
        ansi_goto(MOVE_ROW[sel] + r, MOVE_COL[sel]);
        uart_puts(CURSOR_SEL[r]);
    }
}

// Replaces the dialog area with a message
void update_dialog(const char * const *rows)
{
    int r, i;
    for (r = 0; r < DIALOG_ROWS; r++) {
        ansi_goto(DIALOG_ROW + r, DIALOG_COL);
        for (i = 0; i < DIALOG_W; i++) uart_putc(' ');  
        if (rows[r] && rows[r][0]) {
            ansi_goto(DIALOG_ROW + r, DIALOG_COL);
            uart_puts(rows[r]);
        }
    }
}

// Regenerate sprinte for animation
void update_sprite(int is_player, const char * const *sprite)
{
    int row = is_player ? P_SPRITE_ROW : E_SPRITE_ROW;
    int col = is_player ? P_SPRITE_COL : E_SPRITE_COL;
    int i;
    for (i = 0; sprite[i]; i++) {
        ansi_goto(row + i, col);
        uart_puts(sprite[i]);
    }
}

// Faint 
static void clear_sprite_region(int is_player, int nrows)
{
    int row = is_player ? P_SPRITE_ROW : E_SPRITE_ROW;
    int col = is_player ? P_SPRITE_COL : E_SPRITE_COL;
    int r, i;
    for (r = 0; r < nrows; r++) {
        ansi_goto(row + r, col);
        for (i = 0; i < SPRITE_CLEAR_W; i++) uart_putc(' ');
    }
}

// animation --> regenerates sprite 3 times then erases it
static void faint_animate(int is_player, const char * const *sprite, int nrows)
{
    int flash;
    for (flash = 0; flash < 3; flash++) {
        clear_sprite_region(is_player, nrows);
        SysCtlDelay(SysCtlClockGet() / 60);   // ~17 ms 
        update_sprite(is_player, sprite);
        SysCtlDelay(SysCtlClockGet() / 60);   // ~17 ms 
    }
    clear_sprite_region(is_player, nrows);   
}

// Music playback
volatile uint32_t ui32Period;                  // current half-period in cycles
volatile uint8_t  beat;                        // current note index (S = 0 = silence)
volatile uint32_t seq;                         // index of current pair
volatile uint32_t LEN;                         // current track's pair count
volatile uint32_t TEMPO;                       // current track's ms-per-len
volatile uint32_t ticks_left;                  // ISR firings remaining for this beat
volatile const uint8_t *track_seq;             // pointer to current track's bytes

volatile uint32_t       g_music_state = 0;     // playlist index
volatile int            g_muted       = 0;     // mute toggle

static uint32_t compute_ticks(uint8_t len)
{
    uint32_t hz = F_CPU / ui32Period;          // current ISR rate
    uint32_t t  = (len * TEMPO * hz) / 1000;
    return (t == 0) ? 1 : t;
}

void Timer0IntHandler(void)
{
    TimerIntClear(TIMER0_BASE, TIMER_TIMA_TIMEOUT);

    // Pin toggle
    if (GPIOPinRead(GPIO_PORTB_BASE, GPIO_PIN_5) || (beat == S) || g_muted) {
        GPIOPinWrite(GPIO_PORTB_BASE, GPIO_PIN_5, 0);
    } else {
        GPIOPinWrite(GPIO_PORTB_BASE, GPIO_PIN_5, 0x20);
    }

    // Sequencer
    if (--ticks_left == 0) {
        seq++;
        if (seq >= LEN) seq = 0;                                // loop track
        beat = track_seq[seq * 2];
        uint8_t len = track_seq[seq * 2 + 1];
        ui32Period = (beat == S) ? (F_CPU / 1000) / 2 : notes[beat - 1];
        ticks_left = compute_ticks(len);
        TimerLoadSet(TIMER0_BASE, TIMER_A, ui32Period - 1);
    }
}

static void Music_initialize(void)
{
    SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOB);
    GPIOPinTypeGPIOOutput(GPIO_PORTB_BASE, GPIO_PIN_5);
    GPIOPinWrite(GPIO_PORTB_BASE, GPIO_PIN_5, 0);

    SysCtlPeripheralEnable(SYSCTL_PERIPH_TIMER0);
    TimerConfigure(TIMER0_BASE, TIMER_CFG_PERIODIC);
    TimerEnable(TIMER0_BASE, TIMER_A);

    // Load first
    track_seq = PLAYLIST[g_music_state].seq;
    LEN = PLAYLIST[g_music_state].len;
    TEMPO = PLAYLIST[g_music_state].tempo;
    seq = 0;
    beat = track_seq[0];
    ui32Period = (beat == S) ? (F_CPU / 1000) / 2 : notes[beat - 1];
    ticks_left = compute_ticks(track_seq[1]);

    TimerLoadSet(TIMER0_BASE, TIMER_A, ui32Period - 1);
    IntEnable(INT_TIMER0A);
    TimerIntEnable(TIMER0_BASE, TIMER_TIMA_TIMEOUT);
    IntMasterEnable();
}

// Entry point
int main(void)
{
    int i;
    int sel = 0; // main menu cursor position
    int joy_moved = 0; // 1 if joystick on main menu has moved
    int sel_move = 0; // attack menu cursor position
    int joy_moved_sub = 0; // 1 if joystick on attack menu has moved
    int move_choice = 0;
    int enemy_hp = 20;
    int player_hp = 20;
    int defense_drops = 0;   // Tail Whip stacks
    int attack_drops = 0;   // Growl stacks
    game_state_t state  = STATE_MENU;
    uint32_t x, y;

    UART_initialize();
    ADC_initialize();
    Music_initialize();

    // Wait for GPIO to settle and SW1 to be clearly not pressed
    SysCtlDelay(SysCtlClockGet() / 30);
    while (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0) {}

    // Render full battle scene
    uart_puts("\033[2J\033[H");
    for (i = 0; SCENE[i]; i++) {
        uart_puts(SCENE[i]);
        uart_puts("\r\n");
    }

    while (1) {

        // Menu: joystick moves cursor, SW1 confirms selection
        if (state == STATE_MENU) {
            x = read_adc_ch(ADC_CTL_CH0);
            y = read_adc_ch(ADC_CTL_CH1);

            if (!joy_moved) {
                int row     = sel / 2;
                int col     = sel % 2;
                int new_row = row;
                int new_col = col;

                if (y < JOY_LO) new_row = 0;
                else if (y > JOY_HI) new_row = 1;
                if (x < JOY_LO) new_col = 0;
                else if (x > JOY_HI) new_col = 1;

                {
                    int new_sel = new_row * 2 + new_col;
                    if (new_sel != sel) {
                        update_move_cursor(sel, new_sel);
                        sel = new_sel;
                        joy_moved = 1;
                    }
                }
            } else {
                if (x > JOY_LO && x < JOY_HI && y > JOY_LO && y < JOY_HI)
                    joy_moved = 0;
            }

            if (sw1_pressed()) {
                if (sel == 0) {   // FIGHT, open move sub-menu
                    sel_move      = 0;
                    joy_moved_sub = 0;
                    show_menu(MOVE_LABELS, sel_move);
                    update_dialog(DIALOG_CHOOSE);
                    state = STATE_MOVE_SELECT;
                }
                // BAG / POKEMON / RUN:
                while (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0) {}
            }

            if (sw2_pressed()) {
                g_music_state = (g_music_state + 1) % PLAYLIST_LEN;
                track_seq = PLAYLIST[g_music_state].seq;
                LEN = PLAYLIST[g_music_state].len;
                TEMPO = PLAYLIST[g_music_state].tempo;
                seq = 0;
                ticks_left = 1;            // force ISR to advance into the new track
                while (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_0) == 0) {}
            }

            if (GPIOPinRead(GPIO_PORTB_BASE, GPIO_PIN_0) == 0) {
                SysCtlDelay(SysCtlClockGet() / 150);   // debounce
                if (GPIOPinRead(GPIO_PORTB_BASE, GPIO_PIN_0) == 0) {
                    g_muted = !g_muted;
                    while (GPIOPinRead(GPIO_PORTB_BASE, GPIO_PIN_0) == 0) {}
                }
            }

            SysCtlDelay(SysCtlClockGet() / 300);
        }

        // Move sub-menu: joystick + SW1 pick a move
        else if (state == STATE_MOVE_SELECT) {
            x = read_adc_ch(ADC_CTL_CH0);
            y = read_adc_ch(ADC_CTL_CH1);

            if (!joy_moved_sub) {
                int row     = sel_move / 2;
                int col     = sel_move % 2;
                int new_row = row;
                int new_col = col;

                if (y < JOY_LO) new_row = 0;
                else if (y > JOY_HI) new_row = 1;
                if (x < JOY_LO) new_col = 0;
                else if (x > JOY_HI) new_col = 1;

                {
                    int new_sel = new_row * 2 + new_col;
                    if (new_sel != sel_move) {
                        update_move_cursor(sel_move, new_sel);
                        sel_move = new_sel;
                        joy_moved_sub = 1;
                    }
                }
            } else {
                if (x > JOY_LO && x < JOY_HI && y > JOY_LO && y < JOY_HI)
                    joy_moved_sub = 0;
            }

            if (sw1_pressed()) {
                move_choice = sel_move;
                state = STATE_PLAYER_ATK;
                while (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0) {}
            }

            SysCtlDelay(SysCtlClockGet() / 300);
        }

        // Player executes chosen move
        else if (state == STATE_PLAYER_ATK) {
            int damage = 0;
            if (move_choice == 0) {          // Water Gun
                update_dialog(DIALOG_SQURT_ATK);
                damage = 7 + 2 * defense_drops;
                delay_sec(2);
                enemy_hp -= damage;
                if (enemy_hp < 0) enemy_hp = 0;
                update_hp_bar(0, enemy_hp, 20);
                update_hp_num(0, enemy_hp, 20);
                delay_sec(1);
            } else if (move_choice == 1) {   // Tail Whip — lower enemy defense
                update_dialog(DIALOG_TAIL_WHIP);
                delay_sec(2);
                defense_drops++;
                update_dialog(DIALOG_DEF_DROP);
                delay_sec(2);
            } else if (move_choice == 2) {   // Tackle
                update_dialog(DIALOG_TACKLE);
                damage = 4 + 2 * defense_drops;
                delay_sec(2);
                enemy_hp -= damage;
                if (enemy_hp < 0) enemy_hp = 0;
                update_hp_bar(0, enemy_hp, 20);
                update_hp_num(0, enemy_hp, 20);
                delay_sec(1);
            } else {                         // Growl — lower enemy attack
                update_dialog(DIALOG_GROWL);
                delay_sec(2);
                attack_drops++;
                update_dialog(DIALOG_ATK_DROP);
                delay_sec(2);
            }
            state = (enemy_hp == 0) ? STATE_WIN : STATE_ENEMY_ATK;
        }

        // Enemy counterattacks
        else if (state == STATE_ENEMY_ATK) {
            int dmg = 8 - 2 * attack_drops;
            if (dmg < 1) dmg = 1;
            update_dialog(DIALOG_BULB_ATK);
            delay_sec(2);
            player_hp -= dmg;
            if (player_hp < 0) player_hp = 0;
            update_hp_bar(1, player_hp, 20);
            update_hp_num(1, player_hp, 20);
            delay_sec(1);
            if (player_hp == 0) {
                state = STATE_LOSE;
            } else {
                // Restore main menu labels and cursor
                show_menu(MAIN_LABELS, sel);
                update_dialog(DIALOG_IDLE);
                state = STATE_MENU;
            }
        }

        // Win
        else if (state == STATE_WIN) {
            faint_animate(0, bulbasaur, E_SPRITE_ROWS);
            update_dialog(DIALOG_BULB_FAINT);
            delay_sec(2);
            update_dialog(DIALOG_WIN);
            while (1) {}
        }

        // Lose
        else if (state == STATE_LOSE) {
            faint_animate(1, squirtle, P_SPRITE_ROWS);
            update_dialog(DIALOG_SQURT_FAINT);
            delay_sec(2);
            update_dialog(DIALOG_LOSE);
            while (1) {}
        }
    }
    return 0;
}
