# Core Concepts in `final_project/main.c`

This is a developer reference. It walks through every hardware concept the
project uses and ties each one back to the homework that introduced it, so new
code added to the project follows the same style.

For build / flash / run instructions, see `README.md`.

## House-style summary

| Pattern                     | Choice in this project              | Reference HW          |
|-----------------------------|-------------------------------------|-----------------------|
| Register access             | TivaWare driverlib (not raw macros) | hw3a, uart            |
| UART TX                     | Polled, blocking (`UARTCharPut`)    | uart, hw3a            |
| Switch debouncing           | Two-sample with `SysCtlDelay`       | hw3a                  |
| GPIO init                   | clock-gate → unlock → DEN/DIR/PUR   | hw2a                  |
| Periodic interrupt          | `TIMER_CFG_PERIODIC` + ISR clears flag first | hw4a         |
| ISR / `main` shared state   | `volatile` globals                  | hw4a                  |
| System clock                | 40 MHz (`SYSDIV_5 \| USE_PLL`)      | hw2a, hw3a            |

The project is **all polled I/O except for Timer0** (used to synthesize music
tones). UART, switches, and ADC are all sampled in the main loop.

---

## 1. System clock

`main.c:30, 39-40`

```c
#define F_CPU 40000000UL
SysCtlClockSet(SYSCTL_SYSDIV_5 | SYSCTL_USE_PLL |
               SYSCTL_XTAL_16MHZ | SYSCTL_OSC_MAIN);
```

400 MHz PLL ÷ 10 (`SYSDIV_5`) = 40 MHz. `F_CPU` is used directly by Timer0
period math; everywhere else the runtime value is read with
`SysCtlClockGet()` so delays and baud-rate calculations stay correct if the
clock is ever changed.

Same setup as `hw2a/hw2a.c:23-43` and `hw3a/hw3a.c`.

---

## 2. UART serial communication

### Init — `main.c:37-48`

```c
SysCtlPeripheralEnable(SYSCTL_PERIPH_UART0);
SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOA);
GPIOPinConfigure(GPIO_PA0_U0RX);
GPIOPinConfigure(GPIO_PA1_U0TX);
GPIOPinTypeUART(GPIO_PORTA_BASE, GPIO_PIN_0 | GPIO_PIN_1);
UARTConfigSetExpClk(UART0_BASE, SysCtlClockGet(), 115200,
    UART_CONFIG_WLEN_8 | UART_CONFIG_STOP_ONE | UART_CONFIG_PAR_NONE);
```

Order matters: the peripheral and its GPIO port both need their clocks gated
on before any of their registers can be touched. After that, PA0/PA1 are
mapped to U0RX/U0TX, the alternate function is enabled and the pins are
digitally enabled by `GPIOPinTypeUART`, and the baud-rate divisor and line
control register are programmed by `UARTConfigSetExpClk`.

Settings: **115200 baud, 8 data bits, 1 stop bit, no parity** — same as
`uart/main.c:82-97` and `hw3a`.

### Helpers — `main.c:51-77`

- `uart_putc(c)` — wraps `UARTCharPut`, which spins on the TX FIFO until
  there is room. Blocking, polled.
- `uart_puts(s)` — loops `uart_putc` over a null-terminated string.
- `uart_putint(n)` — writes a non-negative `int` as ASCII digits.
- `ansi_goto(row, col)` — emits the VT100 cursor-position escape
  `ESC [ row ; col H`. Used everywhere updates need to land in a specific
  cell of the battle scene without redrawing the whole screen.

The screen is cleared once at startup with `"\033[2J\033[H"`, then every
subsequent update (HP bars, cursor glyph, dialog text, sprite frames) is a
small partial redraw with an `ansi_goto` followed by some text.

No `UART0_Handler` is wired — the startup table leaves that vector slot at
`IntDefaultHandler`. If a future feature needs RX, this is where to switch
to interrupt-driven I/O.

---

## 3. GPIO initialization and PF0 NMI unlock

`main.c:80-104` (`ADC_initialize`, which also configures the GPIO pins for the
joystick, mute button, and SW1/SW2)

The full sequence used for **every** GPIO port in this project:

1. `SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOx)` — gate the port's clock on.
2. *(PF0 only)* unlock the commit register — see below.
3. `GPIOPinTypeGPIOInput` / `Output` / `UART` / `ADC` — sets `DEN`, `DIR`,
   `AFSEL` as appropriate for the pin's role.
4. `GPIOPadConfigSet(..., GPIO_PIN_TYPE_STD_WPU)` — enables the internal
   pull-up via `PUR` for digital inputs that are wired to active-low buttons.

### Why PF0 needs unlocking — `main.c:97-100`

```c
HWREG(GPIO_PORTF_BASE + GPIO_O_LOCK) = GPIO_LOCK_KEY;
HWREG(GPIO_PORTF_BASE + GPIO_O_CR)  |= GPIO_PIN_0;
HWREG(GPIO_PORTF_BASE + GPIO_O_LOCK) = 0;
```

PF0 is shared with the NMI signal on the TM4C123, so the chip ships with PF0
write-protected. The three-line dance — write the magic key `0x4C4F434B`
("LOCK" in ASCII) to `GPIO_PORTF_LOCK_R`, set the matching bit in the
commit register `GPIO_PORTF_CR_R`, then re-lock — is the official unlock
sequence and is required before anything else (DEN, DIR, PUR) on PF0 will
take effect. PF4 does not need this, but PF0 (SW2) does.

This is the only place in the file that bypasses driverlib and writes
registers directly via `HWREG`, because there is no driverlib wrapper for
the unlock sequence.

Same pattern as `hw2a/hw2a.c:23-43`.

---

## 4. Switch debouncing

`main.c:122-138` (SW1, SW2) and `432-438` (mute button on PB0)

```c
static int sw1_pressed(void)
{
    if (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0) {
        SysCtlDelay(SysCtlClockGet() / 150);   /* ~20 ms debounce */
        return (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0);
    }
    return 0;
}
```

This is the **two-sample debounce** from `hw3a/hw3a.c:139-158`:

1. Read the pin. If it is HIGH, the button is not pressed — return.
2. If LOW, wait long enough for contact bounce to settle.
3. Read again. Return "pressed" only if the second sample is also LOW.

The delay constant deserves a note. `SysCtlDelay(N)` runs a 3-cycle inner
loop, so

```
SysCtlDelay(SysCtlClockGet() / 150)
  = SysCtlDelay(40_000_000 / 150)
  = SysCtlDelay(266_666)
  → 3 × 266_666 = 800_000 cycles
  → 800_000 / 40_000_000 s = 20 ms
```

So the in-source comment "~20 ms" is correct.

After a confirmed press, the call sites also **spin-wait for release** (e.g.
`while (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0) {}`) so a held button
fires only once.

Polled, not interrupt-driven — the project does not register a
`GPIOPortF_Handler`. If you add one, it would replace the `sw1_pressed` /
`sw2_pressed` calls in the main loop, not run alongside them.

---

## 5. ADC — joystick sampling

### Init — `main.c:80-88`

```c
SysCtlPeripheralEnable(SYSCTL_PERIPH_ADC0);
SysCtlPeripheralEnable(SYSCTL_PERIPH_GPIOE);
GPIOPinTypeADC(GPIO_PORTE_BASE, GPIO_PIN_3 | GPIO_PIN_2);
ADCSequenceConfigure(ADC0_BASE, 3, ADC_TRIGGER_PROCESSOR, 0);
ADCSequenceStepConfigure(ADC0_BASE, 3, 0,
                         ADC_CTL_CH0 | ADC_CTL_IE | ADC_CTL_END);
ADCSequenceEnable(ADC0_BASE, 3);
```

We use **sequence 3** because it is one-step deep, which matches our needs
(a single channel sampled on demand). `ADC_TRIGGER_PROCESSOR` means
conversions are kicked off in software rather than by a timer or comparator.
`ADC_CTL_IE | ADC_CTL_END` marks the step as the last one in the sequence
and asks the ADC to set its raw interrupt-status flag when it finishes — we
don't take an actual interrupt; we just poll that flag.

PE2 and PE3 are the two joystick axes; both are configured as analog inputs
by `GPIOPinTypeADC` (it clears `DEN` and `AMSEL` on those pins).

### Sampling — `main.c:106-116`

```c
static uint32_t read_adc_ch(uint32_t ch)
{
    uint32_t val;
    ADCSequenceStepConfigure(ADC0_BASE, 3, 0, ch | ADC_CTL_IE | ADC_CTL_END);
    ADCIntClear(ADC0_BASE, 3);
    ADCProcessorTrigger(ADC0_BASE, 3);
    while (!ADCIntStatus(ADC0_BASE, 3, false)) {}
    ADCIntClear(ADC0_BASE, 3);
    ADCSequenceDataGet(ADC0_BASE, 3, &val);
    return val;
}
```

Each call rewrites step 0 with the requested channel, clears any stale
status, software-triggers the conversion, busy-waits on the status flag,
clears it again, and reads the result out of the sequence FIFO. Callers use
`ADC_CTL_CH0` (PE3, X axis) and `ADC_CTL_CH1` (PE2, Y axis).

### Thresholds — `main.c:33-34`

```c
#define JOY_LO   800
#define JOY_HI  3200
```

The ADC is 12-bit (0-4095), centered around ≈2048. Anything below
`JOY_LO` reads as "down/left," anything above `JOY_HI` reads as "up/right,"
and values in between are treated as centered. This bakes in the dead-zone
without any extra arithmetic.

---

## 6. Timer0 periodic interrupt (music)

This is the only interrupt the project actually uses. It generates a square
wave on PB5 at the frequency of the current note, advancing through a track
of `note_t { freq_hz, dur_ms }` records.

### Shared state — `main.c:285-288`

```c
volatile uint32_t g_ticks_left;
volatile uint32_t g_note_idx;
volatile uint32_t g_music_state = 0;  // current track index
volatile int      g_muted       = 0;
```

`volatile` is mandatory: these are read and written by both the ISR and
`main`, and without `volatile` the compiler is free to cache them in
registers. Same convention as `hw4a/hw4a.c`.

### ISR — `main.c:290-321`

```c
void Timer0IntHandler(void)
{
    TimerIntClear(TIMER0_BASE, TIMER_TIMA_TIMEOUT);   // <-- always first
    ...
    /* toggle PB5 to make a square wave */
    /* decrement g_ticks_left, advance to next note when it hits 0 */
}
```

The first thing every ISR in this codebase does is acknowledge the
interrupt — call `TimerIntClear` (or the equivalent) before doing any
work. Forgetting this re-fires the ISR forever.

The ISR runs at twice the note's frequency (one toggle per half period), so
the reload value is `period = F_CPU / (2 * f)` and the count of ISR ticks
needed to play a note of `d` milliseconds is `d * f * 2 / 1000`.

For a "rest" (`f == 0`) the speaker is held LOW and a 1 kHz timer rate is
used purely to count the rest's duration in milliseconds.

### Init — `main.c:323-349`

```c
SysCtlPeripheralEnable(SYSCTL_PERIPH_TIMER0);
TimerConfigure(TIMER0_BASE, TIMER_CFG_PERIODIC);
TimerLoadSet(TIMER0_BASE, TIMER_A, period - 1);
TimerEnable(TIMER0_BASE, TIMER_A);
IntEnable(INT_TIMER0A);
TimerIntEnable(TIMER0_BASE, TIMER_TIMA_TIMEOUT);
IntMasterEnable();
```

The order matches `hw4a/hw4a.c:49-73`:

1. Gate the timer clock on.
2. Configure the timer mode (periodic = auto-reload).
3. Load the period.
4. Start the timer.
5. Unmask the timer's vector in the NVIC (`IntEnable`).
6. Tell the timer to actually generate interrupts on timeout.
7. Enable interrupts globally.

Steps 5-7 are independent locks; the timer interrupt only fires when
all three are open.

The handler is wired into the vector table at
`tm4c123gh6pm_startup_ccs.c:108`.

---

## 7. Main loop / state machine

`main.c:352-555`

### Init phase

```c
UART_initialize();
ADC_initialize();
Music_initialize();
SysCtlDelay(SysCtlClockGet() / 30);                       // settle
while (GPIOPinRead(GPIO_PORTF_BASE, GPIO_PIN_4) == 0) {}  // wait for SW1 release
uart_puts("\033[2J\033[H");
/* render the full battle scene once */
```

After bringing up the peripherals we wait for SW1 to be released so a
lingering reset-press doesn't immediately register as a menu selection,
then clear the terminal and print the pre-rendered scene from
`scene_data.h`. From this point on, the scene is updated only by partial
redraws.

### States

```c
typedef enum { STATE_MENU, STATE_MOVE_SELECT, STATE_PLAYER_ATK,
               STATE_ENEMY_ATK, STATE_WIN, STATE_LOSE } game_state_t;
```

The main loop is one big `switch (state)` with no blocking calls except
the per-iteration delay and the post-press spin-waits in `sw*_pressed`
callers.

### Hysteresis / debounce for the joystick

The joystick is analog and held in a direction is read as "pushed" on every
loop iteration, which would cause the cursor to fly across the menu. The
fix is a simple hysteresis flag (`joy_moved`, `joy_moved_sub`):

- A direction registers as a "move" only when it is the first deflection
  since the joystick was last centered.
- The flag is cleared the next time the ADC reads a centered value.

This is the analog equivalent of the digital debounce in `sw1_pressed`.

### Loop pacing

Every iteration ends with `SysCtlDelay(SysCtlClockGet() / 300)` (~3.3 ms).
That's slow enough to keep the UART output legible and fast enough to
feel responsive on the joystick.

---

## Where to look for each concept

| Concept                          | Lines (`main.c`)        | HW reference          |
|----------------------------------|-------------------------|-----------------------|
| Clock setup                      | 30, 39-40               | hw2a:23-43, hw3a      |
| UART init + helpers              | 37-77                   | uart:82-97, hw3a      |
| GPIO init pattern                | 80-104                  | hw2a:23-43            |
| PF0 NMI unlock                   | 97-100                  | hw2a                  |
| Switch debounce (SW1/SW2)        | 122-138                 | hw3a:139-158          |
| Mute-button debounce (PB0)       | 432-438                 | hw3a:139-158          |
| ADC sequence configure           | 80-88                   | (project-introduced)  |
| ADC busy-wait sample             | 106-116                 | (project-introduced)  |
| Timer0 ISR                       | 290-321                 | hw4a:49-73            |
| Timer0 init                      | 323-349                 | hw4a:49-73            |
| Main-loop state machine          | 352-555                 | (project-specific)    |
| Vector table / handler wiring    | `tm4c123gh6pm_startup_ccs.c:108` | hw4a startup |
