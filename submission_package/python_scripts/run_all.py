from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
PY = sys.executable

commands = [
    [PY, str(SCRIPTS / "prep_data.py")],
    [PY, str(SCRIPTS / "run_cnn_predict.py")],
    [PY, str(SCRIPTS / "fuse_and_clamp.py")],
    [PY, str(SCRIPTS / "validate_metrics.py")],
]

for cmd in commands:
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)}")

print("All pipeline steps completed successfully.")
