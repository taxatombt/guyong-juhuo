import sys, io, os

# Force UTF-8 output on Windows (fixes GBK console issues with emoji)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add juhuo dir to path
_JUHUO_DIR = r'E:\juhuo'
sys.path.insert(0, _JUHUO_DIR)
os.chdir(_JUHUO_DIR)

# Import and run CLI
from cli import main

if __name__ == '__main__':
    main()
