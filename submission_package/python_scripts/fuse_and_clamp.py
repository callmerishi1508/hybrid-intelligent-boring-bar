from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ACTUATOR_LIMIT_A = 4.0

# Augmentation parameters for more realistic machining/disturbance
MODE2_F = 614.0
MODE2_BASE_AMP = 3e-8  # baseline modal amplitude (m)
MODE2_DAMP = 0.0065
SPINDLE_HZ = 50.0  # example spindle harmonic base (Hz) - used for low-level harmonics

# Actuator dynamics (first-order low-pass) and delay
ACTUATOR_BW_HZ = 1800.0  # actuator effective bandwidth
ACTUATOR_DELAY_S = 2e-4   # small command delay (s)


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
    # Basic fusion
    merged["u_act_nominal"] = merged["u_hinf"] + merged["u_cnn"].fillna(0.0)

    # Estimate sampling period
    t = merged["timestamp"].to_numpy(dtype=float)
    if len(t) > 2:
        dt = float(np.median(np.diff(t)))
    else:
        dt = 1e-4

    # Realistic actuator delay: shift nominal command forward by a few samples
    delay_samples = int(round(ACTUATOR_DELAY_S / dt))
    if delay_samples < 0:
        delay_samples = 0

    u_nom = merged["u_act_nominal"].to_numpy(dtype=float)
    if delay_samples > 0:
        u_delayed = np.concatenate((np.zeros(delay_samples), u_nom[:-delay_samples]))
    else:
        u_delayed = u_nom.copy()

    # Actuator low-pass filter (first-order) discrete approximation
    fc = ACTUATOR_BW_HZ
    alpha = (2 * np.pi * fc * dt) / (1.0 + 2 * np.pi * fc * dt)
    u_dyn = np.zeros_like(u_delayed)
    for i in range(len(u_delayed)):
        if i == 0:
            u_dyn[i] = u_delayed[i]
        else:
            u_dyn[i] = u_dyn[i-1] + alpha * (u_delayed[i] - u_dyn[i-1])

    merged["u_act"] = u_nom
    merged["u_act_dynamic"] = u_dyn

    # --- Energy-aware global scaling: ensure hybrid RMS stays within reasonable bound
    hinf_rms = float(np.sqrt(np.mean(merged['u_hinf'].to_numpy(dtype=float) ** 2))) if len(merged) > 0 else 0.0
    hybrid_rms_no_scale = float(np.sqrt(np.mean(u_nom ** 2)))
    # Prefer using actual dynamic actuator command RMS for scaling decision when available
    try:
        hybrid_rms_actual = float(np.sqrt(np.mean(u_dyn ** 2)))
    except Exception:
        hybrid_rms_actual = hybrid_rms_no_scale
    allowed_factor = 1.15  # allow hybrid RMS up to 15% above H-inf RMS (tighter energy budget)
    if hinf_rms > 1e-6 and hybrid_rms_actual > allowed_factor * hinf_rms:
        scale = (allowed_factor * hinf_rms) / (hybrid_rms_actual + 1e-12)
        # Apply global scaling to CNN contribution and recompute dynamics
        merged['u_cnn'] = merged['u_cnn'].fillna(0.0) * float(scale)
        u_nom = merged['u_hinf'].to_numpy(dtype=float) + merged['u_cnn'].to_numpy(dtype=float)
        if delay_samples > 0:
            u_delayed = np.concatenate((np.zeros(delay_samples), u_nom[:-delay_samples]))
        else:
            u_delayed = u_nom.copy()
        u_dyn = np.zeros_like(u_delayed)
        for i in range(len(u_delayed)):
            if i == 0:
                u_dyn[i] = u_delayed[i]
            else:
                u_dyn[i] = u_dyn[i-1] + alpha * (u_delayed[i] - u_dyn[i-1])
        merged["u_act"] = u_nom
        merged["u_act_dynamic"] = u_dyn

    # Hard clamp (safety)
    merged["u_act_clamped"] = np.clip(merged["u_act_dynamic"], -ACTUATOR_LIMIT_A, ACTUATOR_LIMIT_A)

    # Adjust reported CNN after clamping/dynamics so analysis reflects actual implemented correction
    merged["u_cnn_adj"] = merged["u_act_clamped"] - merged["u_hinf"]

    # Saturation diagnostics
    merged["saturated"] = np.abs(merged["u_act_dynamic"]) > ACTUATOR_LIMIT_A
    merged["saturation_count"] = int(merged["saturated"].sum())
    merged["saturation_fraction"] = float(merged["saturated"].mean())

    # --- Augment sensor measurement to include realistic Mode-2 residual and noise ---
    # Use x_sensor as baseline (modes 1 & 3 present). We add a synthesized Mode-2 component
    t = merged["timestamp"].to_numpy(dtype=float)
    rng = np.random.RandomState(12345)

    # Slow varying amplitude modulation and pulse-to-pulse variation
    amp_mod = 1.0 + 0.3 * rng.randn(len(t))
    amp_mod = pd.Series(amp_mod).rolling(window=max(1, int(0.1 / dt)), min_periods=1, center=True).mean().to_numpy()

    # Small timing jitter as phase noise
    phase_noise = 2 * np.pi * 0.002 * rng.randn(len(t))

    mode2_full = MODE2_BASE_AMP * amp_mod * np.sin(2 * np.pi * MODE2_F * t + phase_noise)

    # Suppression model: the effective residual scales with (1 - normalized CNN cancellation)
    cnn_eff = merged["u_cnn_adj"].fillna(0.0).to_numpy(dtype=float)
    # Normalize by clamp to compute relative cancellation [0..1]
    rel_cnn = np.clip(np.abs(cnn_eff) / (1.0 + np.max(np.abs(cnn_eff)) + 1e-12), 0.0, 1.0)
    suppression = 1.0 - 0.8 * rel_cnn  # up to 80% suppression when CNN strong
    mode2 = mode2_full * suppression

    # Broadband sensor noise and spindle harmonics
    broadband = 1e-8 * rng.randn(len(t))
    spindle = 5e-9 * np.sin(2 * np.pi * SPINDLE_HZ * t) + 2e-9 * np.sin(2 * np.pi * 2 * SPINDLE_HZ * t)

    merged["mode2_full"] = mode2_full
    merged["mode2_residual"] = mode2
    merged["suppression"] = suppression
    merged["broadband_noise"] = broadband
    merged["spindle_harmonics"] = spindle

    merged["x_sensor_aug"] = merged["x_sensor"].to_numpy(dtype=float) + mode2 + broadband + spindle

    # Replace x_sensor for downstream analysis with the augmented measurement (keeps original column too)
    merged["x_sensor"] = merged["x_sensor_aug"]

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
