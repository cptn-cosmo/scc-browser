"""PyInstaller entry point (PyInstaller needs a script, not `python -m`)."""

import sys

from scc_browser.__main__ import main

sys.exit(main())
