import sys
from pathlib import Path

# The installer modules live at the project root (installer/python/), not in a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
