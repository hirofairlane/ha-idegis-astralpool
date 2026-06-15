"""Pytest config — make the add-on's Python package importable.

The add-on lives at `rootfs/opt/pool_brain/`. Tests import its modules
directly (e.g. `import health`) by injecting that directory into
`sys.path` before collection.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Insert the rootfs python path so `import health`, `import timer_engine`,
# etc. resolve to the actual add-on source under
# `addon-pool-brain/rootfs/opt/pool_brain/`.
_PKG = Path(__file__).resolve().parent.parent / "rootfs" / "opt" / "pool_brain"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
