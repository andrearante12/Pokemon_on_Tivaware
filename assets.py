import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')

def load(name):
    with open(os.path.join(_DIR, f"{name}.txt")) as f:
        return f.read()

def lines(name):
    return load(name).splitlines()

def available():
    return sorted(f[:-4] for f in os.listdir(_DIR) if f.endswith('.txt'))
