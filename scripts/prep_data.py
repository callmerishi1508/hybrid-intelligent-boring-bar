from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_and_validate(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")
    df = pd.read_csv(path)
    required = ["timestamp", "x_sensor", "u_hinf"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    df[required] = df[required].apply(pd.to_numeric, errors="coerce")
    if df[required].isna().any().any():
        raise ValueError("NaN or non-numeric values found in required columns.")

    if not df["timestamp"].is_monotonic_increasing:
        df = df.sort_values("timestamp").reset_index(drop=True)

    if (df["timestamp"].diff().iloc[1:] <= 0).any():
        raise ValueError("Timestamps must be strictly increasing.")

    return df


def normalize_timestamp(df: pd.DataFrame, max_jitter_frac: float = 0.02) -> pd.DataFrame:
    dt = df["timestamp"].diff().iloc[1:]
    median_dt = float(np.median(dt))
    if median_dt <= 0:
        raise ValueError("Invalid median sampling interval.")

    jitter = np.abs(dt - median_dt) / median_dt
    if jitter.max() > max_jitter_frac:
        target = df["timestamp"].iloc[0] + np.arange(len(df)) * median_dt
        df["timestamp"] = target
    else:
        df["timestamp"] = df["timestamp"].iloc[0] + np.arange(len(df)) * median_dt

    df["dt"] = median_dt
    df["sampling_rate_hz"] = 1.0 / median_dt
    return df


def save_clean_csv(df: pd.DataFrame, destination: Path) -> None:
    columns = ["timestamp", "x_sensor", "u_hinf"]
    df.to_csv(destination, index=False, columns=columns)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Simscape CSV data for CNN prediction.")
    parser.add_argument("--input", default="simscape_export.csv",
                        help="Raw simscape export CSV path.")
    parser.add_argument("--output", default=OUTPUT_DIR / "simscape_export_clean.csv",
                        help="Clean output CSV path.")
    args = parser.parse_args()

    raw_path = Path(args.input)
    out_path = Path(args.output)
    df = load_and_validate(raw_path)
    df = normalize_timestamp(df)
    save_clean_csv(df, out_path)

    summary = {
        "rows": int(len(df)),
        "sampling_rate_hz": float(df["sampling_rate_hz"].iloc[0]),
        "dt_s": float(df["dt"].iloc[0]),
        "min_timestamp": float(df["timestamp"].iloc[0]),
        "max_timestamp": float(df["timestamp"].iloc[-1]),
        "output_csv": str(out_path),
    }
    print("Cleaned Simscape data saved:")
    print(summary)


if __name__ == "__main__":
    main()
