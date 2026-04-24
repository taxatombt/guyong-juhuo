import sys, io, os

# Force UTF-8 output on Windows (fixes GBK console issues with emoji)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# PyInstaller extraction directory (or None when running from source)
_MEIPASS = getattr(sys, '_MEIPASS', None)
if _MEIPASS:
    # Running as PyInstaller bundle
    _ROOT = _MEIPASS
else:
    _ROOT = r'E:\juhuo'

sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# Import and run CLI
from cli import main

if __name__ == '__main__':
    main()
