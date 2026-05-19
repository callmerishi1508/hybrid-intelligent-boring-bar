# Project 7 - Quick Reference Guide

## 🚀 Quick Start (5 min)

### 1. Dry-Run Test (Local, No Azure)
```powershell
python main.py --dry-run --max-rows 20
```
**Output:** JSON telemetry payloads printed to console (safe, no API calls)

### 2. Run All Analysis
```powershell
python scripts/run_all_analysis.py
```
**Output:** 
- Plots: `output/*.png` (9 high-quality validation plots)
- Data: `output/*_metrics.csv` (3 summary tables)
- Report: `output/FINAL_VALIDATION_REPORT.txt`

### 3. Live Azure Digital Twin (Requires Credentials)
```powershell
# Set credentials first (see LIVE_ADT_SETUP.md)
$env:ADT_ENDPOINT = "https://project7-digitaltwin.api.wus2.digitaltwins.azure.net"
$env:ADT_TENANT_ID = "your-tenant-id"
$env:ADT_CLIENT_ID = "your-client-id"
$env:ADT_CLIENT_SECRET = "your-client-secret"
$env:DIGITAL_TWIN_ID = "BoringBar_01"
$env:IOTHUB_DEVICE_CONNECTION_STRING = "device-connection-string"

# Run live telemetry
python main.py --live --max-rows 100 --speed 10.0
```
**Output:** Live property updates in Azure Digital Twins Explorer

---

## 📁 Project Structure

```
Project 7/
├── README.md                          # Project overview
├── LIVE_ADT_SETUP.md                  # Azure integration guide
├── VALIDATION_ANALYSIS_COMPLETE.md    # This is your validation summary!
├── setup.md                           # Environment setup
│
├── boring_bar_params_1.m              # MATLAB H∞ controller
├── boring_bar.slx                     # Simulink model
├── downgrade_slx.py                   # Version compatibility
│
├── cnn.py                             # CNN training & inference
├── config.py                          # Environment configuration
├── main.py                            # Live telemetry runner
├── telemetry_reader.py                # CSV merge & normalization
├── twin_updater.py                    # Azure Digital Twin updates
│
├── scripts/
│   ├── run_all.py                     # Run everything
│   ├── analyze_cnn_performance.py     # CNN analysis
│   ├── analyze_openloop_vs_closedloop.py  # Vibration analysis
│   ├── generate_final_report.py       # Final report
│   └── run_all_analysis.py            # Orchestrator
│
├── output/                            # Generated outputs (gitignore)
│   ├── *.png                          # Validation plots (9 files)
│   ├── *.csv                          # Metrics tables (8 files)
│   └── FINAL_VALIDATION_REPORT.txt    # Comprehensive report
│
├── docs/
│   └── system_architecture.svg        # Architecture diagram
│
├── screenshots/                       # Presentation images (svg placeholders)
│   ├── simulink_model.svg
│   ├── azure_digital_twin_explorer.svg
│   ├── telemetry_dryrun.svg
│   ├── validation_plots.svg
│   └── github_overview.svg
│
├── model_artifacts/                   # CNN model (gitignore)
│   ├── cnn_mode2.keras
│   ├── scaler.joblib
│   └── metadata.json
│
└── .gitignore                         # Ignores .env, output/, model_artifacts/
```

---

## 🎯 Key Commands Reference

| Task | Command | Output |
|------|---------|--------|
| **Test without Azure** | `python main.py --dry-run --max-rows 20` | JSON payloads |
| **Generate all plots** | `python scripts/run_all_analysis.py` | PNG + CSV files |
| **CNN analysis only** | `python scripts/analyze_cnn_performance.py` | CNN plots & metrics |
| **Vibration comparison** | `python scripts/analyze_openloop_vs_closedloop.py` | Frequency analysis |
| **Final report** | `python scripts/generate_final_report.py` | FINAL_VALIDATION_REPORT.txt |
| **CNN training** | `python cnn.py --data output/simscape_export_clean.csv` | Model artifacts |
| **CNN inference test** | `python cnn.py --predict --data output/simscape_export_clean.csv` | Predictions |
| **Live Azure stream** | `python main.py --live --max-rows 500 --speed 1.0` | Azure updates |

---

## 📊 Generated Output Files (After `python scripts/run_all_analysis.py`)

### Plots (Publication Quality, 300 DPI)
1. **cnn_contribution_over_time.png** (374 KB)
   - H∞, CNN, and hybrid signals over time
   - Vibration response comparison

2. **control_effort_comparison.png** (157 KB)
   - Energy and RMS control effort comparison bars

3. **cnn_magnitude_distribution.png** (213 KB)
   - Distribution of CNN correction magnitudes
   - Mean and statistics

4. **saturation_analysis.png** (174 KB)
   - Actuator saturation events
   - Duration distribution

5. **openloop_vs_closedloop.png** (759 KB)
   - Frequency-domain analysis with modal markers
   - Control signal comparison

6. **vibration_attenuation_analysis.png** (437 KB)
   - RMS variation over time
   - Peak-to-peak statistics

7. **dynamic_stiffness_analysis.png** (89 KB)
   - Modal stiffness response

### Data Files
1. **cnn_performance_metrics.csv** (0.31 KB)
   - Energy, RMS, CNN contribution %
   
2. **openloop_vs_closedloop_summary.csv** (0.32 KB)
   - Vibration and control statistics
   
3. **system_components_summary.csv** (0.45 KB)
   - Component status and key metrics

### Report
- **FINAL_VALIDATION_REPORT.txt** (comprehensive text report)

---

## 🔐 Azure Integration (Optional but Recommended)

### Quick Setup
1. **Get your credentials:**
   - ADT instance: `project7-digitaltwin`
   - IoT Hub: `project7-iothub`
   - Device: `boringbar-edge-device`

2. **Create service principal with Azure Digital Twins Data Owner role**

3. **Set environment variables:**
   ```powershell
   $env:ADT_ENDPOINT = "https://project7-digitaltwin.api.wus2.digitaltwins.azure.net"
   $env:ADT_TENANT_ID = "<tenant-id>"
   $env:ADT_CLIENT_ID = "<client-id>"
   $env:ADT_CLIENT_SECRET = "<client-secret>"
   $env:DIGITAL_TWIN_ID = "BoringBar_01"
   $env:IOTHUB_DEVICE_CONNECTION_STRING = "<device-connection-string>"
   ```

4. **Verify credentials:**
   ```powershell
   python -c "from config import ensure_live_credentials; success, msg = ensure_live_credentials(); print('OK' if success else f'FAIL: {msg}')"
   ```

5. **Run live:**
   ```powershell
   python main.py --live --max-rows 50
   ```

6. **Watch in Azure Digital Twins Explorer:**
   - Open Azure Portal → Digital Twins → project7-digitaltwin
   - Navigate to `BoringBar_01` twin
   - Properties update in real-time!

---

## 📈 Presentation & Report Guide

### For Your Report/Presentation
1. **System Overview:**
   - Use `docs/system_architecture.svg`
   - Reference README.md

2. **CNN Performance:**
   - Include `cnn_contribution_over_time.png`
   - Add metrics from `cnn_performance_metrics.csv`

3. **Control Effectiveness:**
   - Include `control_effort_comparison.png`
   - Show `openloop_vs_closedloop.png` (frequency response)

4. **Validation Summary:**
   - Reference `FINAL_VALIDATION_REPORT.txt`
   - Include table from `system_components_summary.csv`

5. **Azure Integration:**
   - Show live updates from Azure Digital Twins Explorer
   - Reference setup guide in LIVE_ADT_SETUP.md

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'X'` | Run: `pip install -r requirements.txt` |
| Plot generation fails | Ensure `output/` directory exists |
| Azure connection fails | Check credentials with: `python -c "from config import ensure_live_credentials; ..."` |
| Plots look wrong | Verify CSV files exist in `output/` folder |
| Encoding error on print | Use PowerShell (not cmd.exe) |

---

## 💡 Tips & Tricks

1. **Speed up analysis:** Use smaller `--max-rows` for testing
   ```powershell
   python main.py --dry-run --max-rows 10
   ```

2. **Accelerate live stream:** Use `--speed` to run faster
   ```powershell
   python main.py --live --speed 10.0  # 10x faster than real-time
   ```

3. **Re-generate plots:** Just run orchestrator again
   ```powershell
   python scripts/run_all_analysis.py
   ```

4. **Use .env file:** Create `.env` in project root with your credentials (won't be pushed)
   ```
   ADT_ENDPOINT=https://project7-digitaltwin.api.wus2.digitaltwins.azure.net
   ADT_TENANT_ID=your-tenant-id
   # etc...
   ```

5. **Check what files were generated:** 
   ```powershell
   ls output/ | where {$_.Extension -eq '.png'} | Measure-Object -Sum Length
   ```

---

## 📚 Documentation Map

- **README.md** — Project overview, features, quick start
- **setup.md** — Installation and environment setup
- **LIVE_ADT_SETUP.md** — Azure Digital Twin integration (detailed!)
- **VALIDATION_ANALYSIS_COMPLETE.md** — Analysis outputs and findings
- **output/FINAL_VALIDATION_REPORT.txt** — Comprehensive technical report
- This file — Quick reference for common tasks

---

## ✅ Verification Checklist

- [ ] Dry-run works: `python main.py --dry-run --max-rows 10`
- [ ] Analysis runs: `python scripts/run_all_analysis.py`
- [ ] Plots generated: Check `output/*.png` (at least 6 files)
- [ ] CSV files created: Check `output/*_metrics.csv`
- [ ] Final report exists: Check `output/FINAL_VALIDATION_REPORT.txt`
- [ ] All pushed to GitHub: Check latest commit is recent

---

## 🎓 For Academic Use

This project is ready for:
- ✅ Project reports and theses
- ✅ Conference presentations
- ✅ Portfolio demonstrations
- ✅ Professor evaluations
- ✅ Further academic research

All code is documented, plots are publication-quality, and methodology is transparent and reproducible.

---

## 🚀 Next Steps

1. **Review validation plots:** Open `output/*.png` in image viewer
2. **Read final report:** Open `output/FINAL_VALIDATION_REPORT.txt`
3. **Try live Azure:** Follow LIVE_ADT_SETUP.md steps
4. **Use plots in report:** Copy PNG files to your document folder
5. **Push to GitHub:** Already done! Check your repository

---

**Happy analyzing! 🎉**

For questions or issues, refer to LIVE_ADT_SETUP.md or check the individual analysis scripts for detailed documentation.

Last Updated: 2026-05-19
