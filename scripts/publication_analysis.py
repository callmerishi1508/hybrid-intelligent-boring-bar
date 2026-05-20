"""
publication_analysis.py

Produce publication-quality plots and tables from generated datasets in
`output/datasets/`.

Plots/Tables generated under `output/publication/`.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import welch, spectrogram
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'output' / 'datasets'
OUT = ROOT / 'output' / 'publication'
OUT.mkdir(parents=True, exist_ok=True)

MODAL_FREQS = [174, 614, 1130]

def load_dataset(name):
    p = DATA_DIR / f"{name}.csv"
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_csv(p)

def mode_energy(signal, fs, center, width=10.0):
    f, P = welch(signal, fs=fs, nperseg=4096)
    idx = (f >= center - width) & (f <= center + width)
    xf = f[idx]
    yp = P[idx]
    if len(xf) < 2:
        return float(np.sum(yp))
    return float(np.sum((yp[1:] + yp[:-1]) * (xf[1:] - xf[:-1]) * 0.5))

def analyze_all():
    scenarios = [p.stem for p in DATA_DIR.glob('*.csv')]
    summary_rows = []
    fs = int(1.0 / 1e-4)

    for s in scenarios:
        log.info(f'Analyzing: {s}')
        df = load_dataset(s)
        t = df['timestamp'].to_numpy()
        x = df['x_sensor'].to_numpy()
        u_h = df['u_hinf'].to_numpy()
        u_c = df['u_cnn'].to_numpy()
        u_act = df['u_act'].to_numpy()

        # Time-domain comparison plot (open-loop reconstructed vs H-inf vs hybrid)
        fig, ax = plt.subplots(3,1, figsize=(10,8), sharex=True)
        ax[0].plot(t, x, color='purple', linewidth=0.6)
        ax[0].set_title(f'{s} - Vibration (Hybrid)')
        ax[1].plot(t, u_h, color='navy', linewidth=0.6); ax[1].set_title('H∞ Control')
        ax[2].plot(t, u_c, color='orange', linewidth=0.6); ax[2].set_title('CNN Correction')
        plt.tight_layout()
        fig.savefig(OUT / f'{s}_time_signals.png', dpi=300)
        plt.close(fig)

        # Mode-2 PSD zoom
        f_o, P_o = welch(x, fs=fs, nperseg=4096)
        mask = (f_o >= 500) & (f_o <= 700)
        fig, ax = plt.subplots(1,1, figsize=(6,3))
        ax.semilogy(f_o[mask], P_o[mask], label='Hybrid')
        ax.axvline(614, color='red', linestyle='--')
        ax.set_title(f'{s} - Mode-2 PSD (500-700 Hz)')
        ax.set_xlabel('Hz'); ax.set_ylabel('PSD')
        fig.savefig(OUT / f'{s}_mode2_psd.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

        # Spectrogram (short window to get time-frequency)
        f, tt, Sxx = spectrogram(x, fs=fs, nperseg=1024, noverlap=768)
        fig, ax = plt.subplots(1,1, figsize=(8,3))
        ax.pcolormesh(tt, f, 10*np.log10(Sxx), shading='gouraud')
        ax.set_ylim([0, 2000])
        ax.set_ylabel('Frequency (Hz)'); ax.set_xlabel('Time (s)')
        ax.set_title(f'{s} - Spectrogram')
        fig.savefig(OUT / f'{s}_spectrogram.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

        # Control effort histogram
        fig, ax = plt.subplots(1,1, figsize=(6,3))
        ax.hist(u_h, bins=100, alpha=0.6, label='H∞')
        ax.hist(u_c, bins=100, alpha=0.6, label='CNN')
        ax.hist(u_act, bins=100, alpha=0.6, label='Hybrid')
        ax.set_title(f'{s} - Control Effort Distribution')
        ax.legend(); fig.savefig(OUT / f'{s}_control_hist.png', dpi=300)
        plt.close(fig)

        # CNN adaptivity plot: envelope and u_c over time
        env = np.abs(np.imag(np.fft.ifft(np.fft.fft(u_c) * np.exp(-1j*np.pi/2)))) if len(u_c)>0 else np.zeros_like(u_c)
        fig, ax = plt.subplots(1,1, figsize=(8,2))
        ax.plot(t, u_c, label='u_cnn', linewidth=0.6)
        ax.set_title(f'{s} - CNN Correction Time Series')
        fig.savefig(OUT / f'{s}_cnn_timeseries.png', dpi=300)
        plt.close(fig)

        # Residual error metrics
        rms_vib = float(np.sqrt(np.mean(x**2)))
        peak2peak = float(np.max(x) - np.min(x))
        mode_energies = {f: mode_energy(x, fs, f) for f in MODAL_FREQS}

        summary_rows.append({
            'scenario': s,
            'rms_vibration': rms_vib,
            'peak_to_peak': peak2peak,
            'mode1_energy': mode_energies[MODAL_FREQS[0]],
            'mode2_energy': mode_energies[MODAL_FREQS[1]],
            'mode3_energy': mode_energies[MODAL_FREQS[2]],
            'max_control': float(np.max(np.abs(u_act))),
        })

    # Save summary table
    pd.DataFrame(summary_rows).to_csv(OUT / 'publication_summary.csv', index=False)
    print('Saved publication outputs to', OUT)


if __name__ == '__main__':
    analyze_all()
