from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cnn import FEATURE_COLUMNS, MODEL_DIR, load_artifacts, make_windows

OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def batch_predict(df: pd.DataFrame, model, sc, meta: dict) -> pd.DataFrame:
    ws = int(meta["window_size"])
    if len(df) < ws:
        raise ValueError(f"Need at least {ws} rows for prediction; got {len(df)}.")

    X, _ = make_windows(df, window_size=ws, need_target=False)
    X_s = sc.transform(X.reshape(-1, X.shape[-1])).reshape(X.shape).astype(np.float32)
    backend = meta.get("backend", "tensorflow")
    if backend == "sklearn":
        X_flat = X_s.reshape(len(X_s), -1)
        preds = model.predict(X_flat).ravel()
    else:
        preds = model.predict(X_s, verbose=0).ravel()

    clamp = float(meta.get("cnn_clamp_A", 1.5))
    preds = np.clip(preds, -clamp, clamp)

    timestamps = df["timestamp"].iloc[ws - 1 :].reset_index(drop=True)
    out = df.iloc[ws - 1 :].reset_index(drop=True)[["timestamp", "x_sensor", "u_hinf"]].copy()
    out["u_cnn"] = preds
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CNN prediction on cleaned Simscape data.")
    parser.add_argument("--input", default="output/simscape_export_clean.csv",
                        help="Cleaned CSV with timestamp, x_sensor, u_hinf.")
    parser.add_argument("--output", default="output/u_cnn_timeseries.csv",
                        help="Output prediction CSV path.")
    parser.add_argument("--metadata", default=str(MODEL_DIR / "metadata.json"),
                        help="Metadata JSON path.")
    args = parser.parse_args()

    csv_path = Path(args.input)
    if not csv_path.exists():
        raise FileNotFoundError(f"Clean CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    model, sc, meta = load_artifacts()

    out = batch_predict(df, model, sc, meta)
    out_path = Path(args.output)
    out.to_csv(out_path, index=False)

    stats = {
        "rows": int(len(out)),
        "input_rows": int(len(df)),
        "window_size": int(meta["window_size"]),
        "sampling_rate_hz": float(1.0 / (df["timestamp"].diff().median())),
        "u_cnn_min_A": float(out["u_cnn"].min()),
        "u_cnn_max_A": float(out["u_cnn"].max()),
        "output_csv": str(out_path),
    }
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
