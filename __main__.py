# -*- coding: utf-8 -*-
"""
guyong-juhuo executable entry point.
Sets UTF-8 encoding before delegating to cli.main().
"""
import sys
import io

# Windows UTF-8 mode: prevent GBK codec errors on Chinese output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from judgment import cli
cli.main()
