import sys
from pathlib import Path

# repo root: .../OpenPeru
ROOT = Path(__file__).resolve().parents[1]

# Ensure root is on sys.path so `import backend` works
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))