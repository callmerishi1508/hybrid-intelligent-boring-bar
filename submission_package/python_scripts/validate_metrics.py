from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def rms(series: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(series))))


def compute_psd(signal: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    n = len(signal)
    window = np.hanning(n)
    xf = np.fft.rfftfreq(n, 1.0 / fs)
    yf = np.fft.rfft(signal * window)
    psd = np.abs(yf) ** 2 / (fs * np.sum(window ** 2) / n)
    return xf, psd


def phase_lag(a: np.ndarray, b: np.ndarray, fs: float) -> float:
    corr = np.correlate(a - a.mean(), b - b.mean(), mode="full")
    lag = corr.argmax() - (len(a) - 1)
    return float(lag / fs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute validation metrics for fused controller outputs.")
    parser.add_argument("--clean", default="output/simscape_export_clean.csv",
                        help="Cleaned Simscape CSV path.")
    parser.add_argument("--fused", default="output/integrated_control.csv",
                        help="Integrated control CSV path.")
    parser.add_argument("--report", default="output/validation_report.json",
                        help="JSON report path.")
    args = parser.parse_args()

    clean = pd.read_csv(args.clean)
    fused = pd.read_csv(args.fused)

    clean = clean.sort_values("timestamp").reset_index(drop=True)
    fused = fused.sort_values("timestamp").reset_index(drop=True)

    dt = float(np.median(np.diff(clean["timestamp"].to_numpy())))
    fs = 1.0 / dt

    if len(clean) != len(fused) or not clean["timestamp"].equals(fused["timestamp"]):
        aligned = pd.merge_asof(
            fused,
            clean[["timestamp", "x_sensor", "u_hinf"]],
            on="timestamp",
            direction="nearest",
            tolerance=dt * 0.5,
        )
        if "x_sensor_y" in aligned.columns and "u_hinf_y" in aligned.columns:
            aligned = aligned.rename(columns={"x_sensor_y": "x_sensor", "u_hinf_y": "u_hinf"})
        if aligned[["x_sensor", "u_hinf"]].isna().any().any():
            aligned = pd.concat([
                fused,
                clean[["timestamp", "x_sensor", "u_hinf"]].iloc[-len(fused) :].reset_index(drop=True),
            ], axis=1)
            aligned = aligned.rename(columns={"x_sensor": "x_sensor", "u_hinf": "u_hinf"})
        x = aligned["x_sensor"].to_numpy(dtype=float)
        u_hinf = aligned["u_hinf"].to_numpy(dtype=float)
    else:
        x = clean["x_sensor"].to_numpy(dtype=float)
        u_hinf = clean["u_hinf"].to_numpy(dtype=float)

    u_cnn = fused["u_cnn"].to_numpy(dtype=float)
    u_act = fused["u_act"].to_numpy(dtype=float)
    u_act_clamped = fused["u_act_clamped"].to_numpy(dtype=float)

    metrics = {
        "sampling_rate_hz": fs,
        "rms_displacement_m": rms(x),
        "control_energy_hinf_J": float(np.sum(np.square(u_hinf)) * dt),
        "control_energy_fused_J": float(np.sum(np.square(u_act_clamped)) * dt),
        "control_energy_reduction_pct": float(
            100.0 * (np.sum(np.square(u_hinf)) - np.sum(np.square(u_act_clamped))) / np.sum(np.square(u_hinf))
        ),
        "rms_u_hinf_A": rms(u_hinf),
        "rms_u_act_clamped_A": rms(u_act_clamped),
        "u_act_saturation_fraction": float(np.mean(np.abs(u_act) > 4.0)),
        "prediction_phase_lag_s": phase_lag(u_hinf, u_act_clamped, fs),
        "u_cnn_min_A": float(np.min(u_cnn)),
        "u_cnn_max_A": float(np.max(u_cnn)),
        "u_act_clamped_min_A": float(np.min(u_act_clamped)),
        "u_act_clamped_max_A": float(np.max(u_act_clamped)),
    }

    f_x, psd_x = compute_psd(x, fs)
    plot_path = OUTPUT_DIR / "validation_time_domain.png"
    plt.figure(figsize=(10, 5))
    plt.plot(fused["timestamp"], x, label="x_sensor")
    plt.plot(fused["timestamp"], u_act_clamped / 1e6, label="u_act_clamped (scaled)")
    plt.xlabel("Time [s]")
    plt.ylabel("Signal")
    plt.title("Time Domain: displacement and fused actuator command")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    plot_path = OUTPUT_DIR / "validation_psd.png"
    plt.figure(figsize=(10, 5))
    plt.semilogx(f_x, 10 * np.log10(psd_x + 1e-20), label="x_sensor PSD")
    plt.xlabel("Frequency [Hz]")
    plt.ylabel("Power/Frequency [dB/Hz]")
    plt.title("PSD of x_sensor")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    report = {
        "metrics": metrics,
        "plots": [
            str(OUTPUT_DIR / "validation_time_domain.png"),
            str(OUTPUT_DIR / "validation_psd.png"),
        ],
    }
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"Saved validation report to {args.report}")


if __name__ == "__main__":
    main()
