"""
generate_datasets.py
Generate multiple synthetic telemetry datasets with varying chatter and noise.

Outputs (per scenario):
 - output/datasets/<scenario>.csv
 - output/datasets/<scenario>.npz (numpy arrays)
 - output/datasets/<scenario>_telemetry.jsonl (JSON telemetry lines)
 - output/datasets/<scenario>_meta.json

Scenarios:
  stable, moderate, severe, variable_spindle, sensor_noise

This generator creates realistically nonstationary Mode-2 energy, spindle harmonics,
colored noise, pulse-to-pulse variance, and small nonlinear growth episodes.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.signal import butter, lfilter
import math

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "datasets"
OUT.mkdir(parents=True, exist_ok=True)

# Modal freqs
MODES = {"m1":174.0, "m2":614.0, "m3":1130.0}
TS = 1e-4  # 10 kHz
FS = int(1.0/TS)
DURATION_S = 4.0
N = int(DURATION_S / TS)

def pink_noise(n, alpha=1.0, seed=None):
    rng = np.random.RandomState(seed)
    # Voss-McCartney like approx via 1/f filtering in frequency domain
    freqs = np.fft.rfftfreq(n, d=TS)
    spectrum = np.zeros_like(freqs)
    spectrum[1:] = 1.0 / (freqs[1:] ** (alpha/2.0))
    phases = rng.normal(size=spectrum.shape) + 1j * rng.normal(size=spectrum.shape)
    spec = spectrum * phases
    x = np.fft.irfft(spec, n=n)
    x = x / (np.std(x) + 1e-12)
    return x

def bandpass(x, center, bw, fs=FS, order=4):
    nyq = 0.5 * fs
    low = max((center - bw/2)/nyq, 1e-6)
    high = min((center + bw/2)/nyq, 0.999)
    b, a = butter(order, [low, high], btype='band')
    return lfilter(b, a, x)

def synth_scenario(name: str):
    t = np.arange(N) * TS
    rng = np.random.RandomState(abs(hash(name)) % (2**32))

    # Base structure: modes 1 & 3 ringdown
    x_base = (
        5e-7 * np.exp(-0.0005 * t) * np.sin(2*np.pi*MODES['m1']*t + rng.randn()*0.1)
        + 1e-7 * np.exp(-0.0002 * t) * np.sin(2*np.pi*MODES['m3']*t + rng.randn()*0.1)
    )

    # Mode-2 envelope depending on scenario
    if name == 'stable':
        m2_env = 0.6 + 0.1 * np.sin(0.5 * t) + 0.05 * rng.randn(N)
        m2_amp = 3e-8 * m2_env
        m2_phase_jitter = 0.001 * rng.randn(N)
    elif name == 'moderate':
        m2_env = 1.0 + 0.6 * (np.tanh(3*(np.sin(0.8*t))) ) + 0.2 * rng.randn(N)
        m2_amp = 6e-8 * np.abs(m2_env)
        m2_phase_jitter = 0.01 * rng.randn(N)
    elif name == 'severe':
        # intermittent bursts via envelope spikes
        bursts = (np.random.RandomState(7).rand(N) > 0.995).astype(float)
        burst_env = 1.0 + 8.0 * np.convolve(bursts, np.exp(-np.arange(0,300)/50.0), mode='same')
        m2_amp = 1.2e-7 * burst_env + 2e-8 * rng.randn(N)
        m2_phase_jitter = 0.02 * rng.randn(N)
    elif name == 'variable_spindle':
        # slowly varying spindle speed causing crossing
        spindle = 40.0 + 30.0 * np.sin(0.2*t)  # Hz
        m2_amp = (4e-8 + 2e-8 * np.sin(2*np.pi*0.5*t))
        m2_phase_jitter = 0.01 * rng.randn(N)
    elif name == 'sensor_noise':
        m2_amp = 3e-8 * (1.0 + 0.1 * rng.randn(N))
        m2_phase_jitter = 0.005 * rng.randn(N)
    else:
        m2_amp = 3e-8 * np.ones(N)
        m2_phase_jitter = 0.001 * rng.randn(N)

    # Mode-2 signal
    mode2 = m2_amp * np.sin(2*np.pi*MODES['m2']*t + m2_phase_jitter)

    # Spindle harmonics
    if name == 'variable_spindle':
        spindle_hz = 40.0 + 30.0 * np.sin(0.2*t)
        spindle = 5e-9 * np.sin(2*np.pi*spindle_hz*t) + 2e-9 * np.sin(2*np.pi*2*spindle_hz*t)
    else:
        spindle_hz = 50.0
        spindle = 5e-9 * np.sin(2*np.pi*spindle_hz*t) + 2e-9 * np.sin(2*np.pi*2*spindle_hz*t)

    # Colored broadband noise
    broadband = 2e-8 * pink_noise(N, alpha=0.8, seed=hash(name) & 0xffffffff)

    # Nonlinear chatter growth for severe
    if name == 'severe':
        nonlin = 1e-7 * np.tanh(5*mode2 / (1e-8 + np.abs(mode2)))
    else:
        nonlin = 0

    # Sensor noise / dropout for sensor_noise scenario
    sensor_noise = 1e-8 * rng.randn(N)
    if name == 'sensor_noise':
        # random dropouts
        drops = (rng.rand(N) > 0.999)
        sensor_noise[drops] += 1e-6

    # x_sensor measured (modes1&3 present + residual mode2 + noise)
    x_sensor = x_base + mode2 + broadband + spindle + nonlin + sensor_noise

    # Simple H-inf proxy control (PD on x_sensor) - does not suppress Mode-2
    u_hinf = np.clip(-2e6 * x_sensor - 30 * np.gradient(x_sensor, TS), -4.0, 4.0)

    # CNN ideal target: approximate cancellation of modal acceleration (with uncertainty)
    q2dd = np.gradient(np.gradient(mode2, TS), TS)
    m2 = 0.147; KI2 = 4.41
    u_cnn_true = np.clip(-(m2/KI2) * q2dd, -1.5, 1.5)

    # Make CNN adaptive and imperfect: add history dependence and uncertainty
    u_cnn_adaptive = u_cnn_true * (0.6 + 0.4 * np.tanh(5*np.convolve(np.abs(mode2), np.ones(50)/50.0, mode='same')))
    u_cnn_adaptive += 0.02 * np.random.RandomState(hash(name) & 0xffffffff).randn(N) * np.abs(u_cnn_adaptive)

    # Energy-aware scaling to avoid excessive actuation
    u_act_nom = u_hinf + u_cnn_adaptive
    u_act = np.clip(u_act_nom, -4.0, 4.0)

    # Residual vibration after hybrid: simulate partial cancellation
    residual_mode2 = mode2 * (1.0 - 0.8 * (np.abs(u_cnn_adaptive) / (1.0 + np.max(np.abs(u_cnn_adaptive)))))
    x_residual = x_base + residual_mode2 + broadband + spindle + nonlin + sensor_noise

    # PSD summary around modal peaks
    def psd_peak(signal, center, width=10.0):
        from scipy.signal import welch
        f, P = welch(signal, fs=FS, nperseg=4096)
        idx = np.logical_and(f >= center - width, f <= center + width)
        xf = f[idx]
        yp = P[idx]
        if len(xf) < 2:
            return float(np.sum(yp))
        # numerical trapezoidal integration without np.trapz
        return float(np.sum((yp[1:] + yp[:-1]) * (xf[1:] - xf[:-1]) * 0.5))

    psd_m2 = psd_peak(x_sensor, MODES['m2'], width=10.0)

    # Create DataFrame and save
    df = pd.DataFrame({
        'timestamp': t,
        'x_sensor': x_sensor,
        'u_hinf': u_hinf,
        'u_cnn': u_cnn_adaptive,
        'u_act': u_act,
        'spindleSpeed': spindle_hz if np.isscalar(spindle_hz) else spindle_hz,
        'mode2_residual': residual_mode2,
    })

    out_csv = OUT / f"{name}.csv"
    out_npz = OUT / f"{name}.npz"
    out_meta = OUT / f"{name}_meta.json"
    out_jsonl = OUT / f"{name}_telemetry.jsonl"

    df.to_csv(out_csv, index=False)
    np.savez_compressed(out_npz, timestamp=t, x_sensor=x_sensor, u_hinf=u_hinf, u_cnn=u_cnn_adaptive, u_act=u_act, mode2_residual=residual_mode2)

    meta = {
        'scenario': name,
        'rows': int(N),
        'Ts': TS,
        'fs': FS,
        'psd_m2': psd_m2,
        'modal_frequencies': MODES,
    }
    out_meta.write_text(json.dumps(meta, indent=2), encoding='utf-8')

    # Telemetry JSONL for Digital Twin demo
    with out_jsonl.open('w', encoding='utf-8') as f:
        for i in range(N):
            pkt = {
                'timestamp': float(t[i]),
                'vibrationAmplitude': float(x_sensor[i]),
                'spindleSpeed': float(spindle_hz[i]) if not np.isscalar(spindle_hz) else float(spindle_hz),
                'cnnCorrection': float(u_cnn_adaptive[i]),
                'actuatorForce': float(u_act[i]),
                'mode2Residual': float(residual_mode2[i]),
            }
            f.write(json.dumps(pkt) + '\n')

    print(f"Generated: {out_csv}  {out_npz}  {out_meta}  {out_jsonl}")


def main():
    scenarios = ['stable', 'moderate', 'severe', 'variable_spindle', 'sensor_noise']
    for s in scenarios:
        synth_scenario(s)


if __name__ == '__main__':
    main()
