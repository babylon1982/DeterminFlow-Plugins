from __future__ import annotations

import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORE_ROOT = PLUGIN_ROOT.parents[2] / "DeterminFlow"
CORE_ROOT = Path(os.getenv("DETERMINFLOW_CORE_ROOT", str(DEFAULT_CORE_ROOT))).resolve()

sys.path.insert(0, str(PLUGIN_ROOT))
if CORE_ROOT.is_dir():
    sys.path.insert(0, str(CORE_ROOT))
