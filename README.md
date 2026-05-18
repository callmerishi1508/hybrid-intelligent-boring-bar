Project 7 — CNN Mode-2 Feedforward
===================================

Quick start
-----------
1. Create a Python virtual environment and activate it.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

Notes: `tensorflow` on Windows may be heavy; `tensorflow-cpu` is listed to provide a CPU-only build.

Run smoke test
--------------

```bash
python cnn.py --smoke
```

This will generate a synthetic CSV, train a small model, run a prediction, and print metrics.

Train on your Simscape export
----------------------------
1. Export from MATLAB/Simscape as CSV with columns: `timestamp`, `x_sensor`, `u_hinf`, `u_cnn`.
2. Run:

```bash
python cnn.py --data simscape_export.csv
```

Predict with saved artifacts
---------------------------

```bash
python cnn.py --predict --data simscape_export.csv
```

VS Code Python interpreter setup
------------------------------
- Open the workspace in VS Code.
- Open the Command Palette (Ctrl+Shift+P) → `Python: Select Interpreter` → choose the `.venv` created above.
- Install the Python extension if prompted.

MATLAB / Simulink
-----------------
- `boring_bar_params_1.m` is present but requires MATLAB (Control System Toolbox / Robust Control / Simulink) to run. I can't execute MATLAB code here.

Files produced
--------------
- `model_artifacts/` — trained model, scaler, and metadata
- `output/` — copies of the artifacts and smoke log

Screenshots
-----------
Presentation-ready screenshots are included in the `screenshots/` folder. These are placeholder images you can replace with high-resolution captures from your environment:

- `screenshots/simulink_model.svg`
- `screenshots/azure_digital_twin_explorer.svg`
- `screenshots/telemetry_dryrun.svg`
- `screenshots/validation_plots.svg`
- `screenshots/github_overview.svg`

Architecture Diagram
--------------------
A system architecture diagram is provided in `docs/system_architecture.svg`. It visualizes the flow:

Simulink/Simscape → H∞ Robust Controller → CNN Optimization → Hybrid Fused Controller → CSV Telemetry Export → Python Telemetry Pipeline → Azure IoT Hub → Azure Digital Twin

Telemetry pipeline
------------------
The `main.py` + `telemetry_reader.py` implements a merged telemetry stream that combines CSV exports (Simscape+CNN+fusion) into a normalized telemetry payload and supports a dry-run mode. This is suitable for demos and integration testing before connecting to live Azure resources (see `setup.md`).

If you want, I can:
- Pin exact package versions into a `pyproject.toml` or `constraints.txt`.
- Create a small `run.sh` / `run.ps1` helper script.
