from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ACTUATOR_LIMIT_A = 4.0


def load_data(clean_csv: Path, cnn_csv: Path) -> pd.DataFrame:
    if not clean_csv.exists():
        raise FileNotFoundError(f"Clean CSV not found: {clean_csv}")
    if not cnn_csv.exists():
        raise FileNotFoundError(f"CNN prediction CSV not found: {cnn_csv}")

    clean = pd.read_csv(clean_csv)
    cnn = pd.read_csv(cnn_csv)
    if "timestamp" not in clean.columns or "timestamp" not in cnn.columns:
        raise ValueError("Both files must contain a timestamp column.")

    clean = clean.sort_values("timestamp").reset_index(drop=True)
    cnn = cnn.sort_values("timestamp").reset_index(drop=True)

    if len(clean) == len(cnn) and np.allclose(clean["timestamp"].to_numpy(), cnn["timestamp"].to_numpy(), rtol=0, atol=1e-9):
        merged = clean.copy()
        merged = merged.merge(cnn[["timestamp", "u_cnn"]], on="timestamp", how="left")
    else:
        dt = float(np.median(np.diff(clean["timestamp"].to_numpy())))
        tolerance = max(dt * 0.5, 1e-6)
        merged = pd.merge_asof(
            clean,
            cnn[["timestamp", "u_cnn"]],
            on="timestamp",
            direction="nearest",
            tolerance=tolerance,
        )

    if merged["u_cnn"].isna().any():
        # Try direct index alignment for windowed predictions.
        if len(clean) >= len(cnn):
            merged = clean.iloc[len(clean) - len(cnn) :].copy().reset_index(drop=True)
            merged["u_cnn"] = cnn["u_cnn"].reset_index(drop=True)
        else:
            raise ValueError("CNN predictions do not align with clean timestamps.")

    return merged[["timestamp", "x_sensor", "u_hinf", "u_cnn"]]

    return merged[["timestamp", "x_sensor", "u_hinf", "u_cnn"]]


def apply_clamp(merged: pd.DataFrame) -> pd.DataFrame:
    merged = merged.copy()
    merged["u_act"] = merged["u_hinf"] + merged["u_cnn"]
    merged["u_act_clamped"] = np.clip(merged["u_act"], -ACTUATOR_LIMIT_A, ACTUATOR_LIMIT_A)
    merged["u_cnn_adj"] = merged["u_act_clamped"] - merged["u_hinf"]
    merged["saturated"] = np.abs(merged["u_act"]) > ACTUATOR_LIMIT_A
    merged["saturation_count"] = int(merged["saturated"].sum())
    merged["saturation_fraction"] = float(merged["saturated"].mean())
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Fuse H-inf and CNN control commands safely.")
    parser.add_argument("--clean", default="output/simscape_export_clean.csv",
                        help="Cleaned Simscape CSV path.")
    parser.add_argument("--cnn", default="output/u_cnn_timeseries.csv",
                        help="CNN prediction CSV path.")
    parser.add_argument("--output", default="output/integrated_control.csv",
                        help="Integrated control CSV output.")
    args = parser.parse_args()

    clean_path = Path(args.clean)
    cnn_path = Path(args.cnn)
    out_path = Path(args.output)

    merged = load_data(clean_path, cnn_path)
    fused = apply_clamp(merged)
    fused.to_csv(out_path, index=False)

    stats = {
        "rows": int(len(fused)),
        "actuator_limit_A": ACTUATOR_LIMIT_A,
        "u_act_min_A": float(fused["u_act"].min()),
        "u_act_max_A": float(fused["u_act"].max()),
        "u_act_clamped_min_A": float(fused["u_act_clamped"].min()),
        "u_act_clamped_max_A": float(fused["u_act_clamped"].max()),
        "saturation_count": int(fused["saturated"].sum()),
        "saturation_fraction": float(fused["saturated"].mean()),
        "output_csv": str(out_path),
    }
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
