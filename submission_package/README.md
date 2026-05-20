# Hybrid H∞ + CNN Intelligent Boring Bar — Submission Package

This repository contains the hybrid H∞ + CNN active vibration suppression project for a CNC boring bar, with Azure Digital Twin integration and publication-quality analysis.

This README provides step-by-step reproduction instructions, folder structure, commands, and expected outputs for academic submission.

## Project Overview
- Hybrid control: H∞ robust baseline + CNN adaptive feedforward for Mode‑2
- Simscape plant model used for simulation and dataset generation
- Edge processing packages telemetry to Azure IoT Hub and patches Azure Digital Twin

## Folder Structure (generated in `submission_package/`)
- simulink_models/ — .slx Simulink model files
- matlab_scripts/ — MATLAB scripts (.m) including H∞ synthesis and helpers
- python_scripts/ — all Python scripts used for analysis, generation, Azure integration
- datasets/ — generated datasets (.csv, .npz, metadata.json, telemetry JSONL)
- output_plots/ — publication-quality figures (PNG/SVG/PDF)
- azure_outputs/ — telemetry JSONL and digital twin event JSONL
- reports/ — FINAL_VALIDATION_REPORT.txt, validation_report.json
- documentation/ — architecture PDF and other docs

## Software Requirements
- Python 3.8+ with: numpy, pandas, matplotlib, scipy, joblib
- MATLAB + Simulink (R2022b or newer recommended) for `boring_bar.slx`
- (Optional) Azure SDKs: `azure-identity`, `azure-digitaltwins-core`, `azure.iot.device` for live integration

## Python dependencies (install via pip)
```bash
pip install numpy pandas matplotlib scipy joblib
# Optional (Azure live mode):
pip install azure-identity azure-digitaltwins-core azure-iot-device
```

## Reproduce all final outputs — exact commands
Run from project root `C:\Project 7`.

1. Generate datasets
```bash
python scripts/generate_datasets.py
```

2. Publication analysis (spectrograms, per-scenario figures)
```bash
python scripts/publication_analysis.py
```

3. Open-loop vs closed-loop analysis (core control plots)
```bash
python scripts/analyze_openloop_vs_closedloop.py
```

4. CNN performance analysis
```bash
python scripts/analyze_cnn_performance.py
```

5. Validation metrics and PSD/time plots
```bash
python scripts/validate_metrics.py --clean output/simscape_export_clean.csv --fused output/integrated_control.csv --report output/validation_report.json
```

6. Generate Azure-compatible telemetry and events
```bash
python scripts/generate_azure_outputs.py
```

7. Assemble final tables and report
```bash
python scripts/generate_final_tables.py
python scripts/generate_final_report.py
```

8. One-line full pipeline
```bash
python scripts/generate_datasets.py && python scripts/publication_analysis.py && python scripts/analyze_openloop_vs_closedloop.py && python scripts/analyze_cnn_performance.py && python scripts/validate_metrics.py --clean output/simscape_export_clean.csv --fused output/integrated_control.csv --report output/validation_report.json && python scripts/generate_azure_outputs.py && python scripts/generate_final_tables.py && python scripts/generate_final_report.py
```

## Expected outputs (selection)
- `output/openloop_vs_closedloop.png` — Core time/frequency control comparison
- `output/mode2_psd_zoom.png` — Mode‑2 (500–700 Hz) PSD zoom
- `output/cnn_contribution_over_time.png` — CNN correction time series
- `output/control_effort_comparison.png` — Energy tradeoff plot
- `output/azure_telemetry.jsonl` — telemetry JSONL (edge → IoT Hub)
- `output/digital_twin_events.jsonl` — event packets (chatter warnings, PM)
- `output/azure_architecture_diagram.pdf` — architecture diagram
- `output/FINAL_VALIDATION_REPORT.txt` — final validation report
- `output/final_performance_table.csv/.tex` — final performance table

## Azure Digital Twin & IoT notes
- Telemetry keys: `vibrationAmplitude`, `spindleSpeed`, `cnnCorrection`, `actuatorForce`, `mode2Residual`, `predictionConfidence`.
- Events: `chatter_warning`, `saturation_alert`, `predictive_maintenance` — saved in `output/digital_twin_events.jsonl`.
- Local buffering behaviour is simulated; the edge buffers telemetry when disconnected and flushes on reconnect.

## Troubleshooting
- If plotting fails, verify `matplotlib` and `scipy` are installed.\
- If `main.py --live` fails, confirm ADT and IoT Hub credentials in `config.py` and environment variables.\
- If Simulink model cannot be opened, verify MATLAB/Simulink version compatibility.

## License & Credits
Project prepared for academic evaluation. See repository for author and license details.
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
