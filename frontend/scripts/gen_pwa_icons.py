"""Deprecated wrapper — homescreen icons use the header SignalMark."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from render_app_icons import main

if __name__ == "__main__":
    main()
