import sys
from pathlib import Path

# Make the `autopilot` package importable when running pytest from the repo
# without an editable install.
ORCH = Path(__file__).resolve().parents[1]
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

REPO_ROOT = ORCH.parents[1]
STACKS_DIR = REPO_ROOT / "stacks"
