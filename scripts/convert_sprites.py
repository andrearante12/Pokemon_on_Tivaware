import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR  = os.path.join(PROJECT_DIR, 'assets')


def _encode_line(line):
    return line.replace('\\', '\\\\').replace('"', '\\"')


def convert(name):
    path = os.path.join(ASSETS_DIR, f'{name}.txt')
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n\r') for l in f.readlines()]

    # strip leading/trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    # strip common left indent
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    lines = [l[indent:].rstrip() for l in lines]

    print(f'static const char *{name}[] = {{')
    for line in lines:
        print(f'    "{_encode_line(line)}",')
    print('    0')
    print('};')
    print()


if __name__ == '__main__':
    for f in sorted(os.listdir(ASSETS_DIR)):
        if f.endswith('.txt'):
            convert(f[:-4])
