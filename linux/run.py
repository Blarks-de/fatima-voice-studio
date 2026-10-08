"""Start Fatima Voice Studio on Linux: applies the compatibility layer, then runs the normal entry point.

  python linux/run.py                 console mode, opens the browser
  python linux/run.py --no-browser    don't open the browser
  python linux/run.py --tray          also show a tray icon (needs a tray / AppIndicator in your desktop)
  python linux/run.py --check         import everything and exit 0
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compat  # noqa: E402

compat.apply()

if "--tray" in sys.argv[1:]:
    from studio import app as _app  # noqa: F401  (imports first: tray needs the patched autostart)
    compat.patch_tray()

from studio.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
