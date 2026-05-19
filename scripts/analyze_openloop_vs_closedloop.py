"""
Open-Loop vs Closed-Loop Analysis
Compare uncontrolled vibration behavior with H∞ and hybrid control.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch, decimate
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")

# Modal frequencies of interest (Hz)
MODAL_FREQUENCIES = [174, 614, 1130]

def load_data():
    """Load telemetry data."""
    log.info("Loading data for open-loop vs closed-loop analysis...")
    
    simscape = pd.read_csv(OUTPUT_DIR / "simscape_export_clean.csv")
    integrated = pd.read_csv(OUTPUT_DIR / "integrated_control.csv")
    
    # Merge
    merged = pd.merge_asof(
        simscape[["timestamp", "x_sensor", "u_hinf"]],
        integrated[["timestamp", "u_cnn", "u_act", "u_act_clamped"]],
        on="timestamp",
        direction="nearest",
        tolerance=1e-4
    )
    
    log.info(f"Loaded {len(merged)} points")
    return merged

def estimate_sampling_rate(df):
    """Estimate sampling rate from timestamp."""
    dt = np.median(np.diff(df['timestamp'].values))
    fs = 1.0 / dt
    log.info(f"Estimated sampling rate: {fs:.2f} Hz")
    return fs

def compute_frequency_response(vibration, fs, freq_range=(0, 2000)):
    """Compute power spectral density."""
    # Convert pandas Series to numpy array
    vibration_array = np.asarray(vibration)
    f, Pxx = welch(vibration_array, fs=fs, nperseg=4096, scaling='density')
    mask = (f >= freq_range[0]) & (f <= freq_range[1])
    return f[mask], Pxx[mask]

def plot_vibration_comparison(df, fs):
    """Plot vibration time-domain and frequency-domain responses."""
    log.info("Generating vibration comparison plots...")
    
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    
    # Time domain - vibration
    ax = fig.add_subplot(gs[0, :])
    ax.plot(df['timestamp'], df['x_sensor'], label='Vibration (Closed-Loop)', linewidth=1, alpha=0.8, color='purple')
    ax.set_ylabel('Vibration Amplitude (m)', fontsize=11, fontweight='bold')
    ax.set_title('Vibration Response - Closed-Loop (H∞ + CNN)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10, loc='upper right')
    ax.grid(True, alpha=0.3)
    
    # Frequency domain - vibration
    ax = fig.add_subplot(gs[1, :])
    f_vib, Pxx_vib = compute_frequency_response(df['x_sensor'], fs)
    ax.semilogy(f_vib, Pxx_vib, label='Vibration Power Spectrum', linewidth=1.5, color='purple')
    
    # Mark modal frequencies
    for freq in MODAL_FREQUENCIES:
        if freq <= max(f_vib):
            ax.axvline(freq, color='red', linestyle='--', alpha=0.5, linewidth=1)
            ax.text(freq, Pxx_vib.max() * 0.1, f'{freq}Hz', rotation=90, fontsize=9, color='red')
    
    ax.set_xlabel('Frequency (Hz)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Power Spectral Density', fontsize=11, fontweight='bold')
    ax.set_title('Vibration Frequency Response - Closed-Loop Control', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10, loc='upper right')
    ax.grid(True, alpha=0.3, which='both')
    ax.set_xlim([0, 2000])
    
    # Control signals in time domain
    ax = fig.add_subplot(gs[2, 0])
    ax.plot(df['timestamp'], df['u_hinf'], label='H∞ Control', linewidth=1, alpha=0.8)
    ax.plot(df['timestamp'], df['u_act_clamped'], label='Hybrid (H∞+CNN)', linewidth=1, alpha=0.8, linestyle='--')
    ax.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Control Signal (A)', fontsize=11, fontweight='bold')
    ax.set_title('Control Signals Comparison', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Control frequency response
    ax = fig.add_subplot(gs[2, 1])
    f_ctrl_h, Pxx_ctrl_h = compute_frequency_response(df['u_hinf'], fs)
    f_ctrl_hybrid, Pxx_ctrl_hybrid = compute_frequency_response(df['u_act_clamped'].fillna(0), fs)
    
    ax.semilogy(f_ctrl_h, Pxx_ctrl_h, label='H∞ Frequency Response', linewidth=1.5)
    ax.semilogy(f_ctrl_hybrid, Pxx_ctrl_hybrid, label='Hybrid Frequency Response', linewidth=1.5, linestyle='--')
    
    for freq in MODAL_FREQUENCIES:
        if freq <= max(f_ctrl_h):
            ax.axvline(freq, color='red', linestyle='--', alpha=0.3, linewidth=1)
    
    ax.set_xlabel('Frequency (Hz)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Power Spectral Density', fontsize=11, fontweight='bold')
    ax.set_title('Control Signal Frequency Content', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, which='both')
    ax.set_xlim([0, 2000])
    
    plt.savefig(OUTPUT_DIR / "openloop_vs_closedloop.png", dpi=300, bbox_inches='tight')
    log.info(f"✓ Saved: output/openloop_vs_closedloop.png")
    plt.close()

def plot_vibration_attenuation(df):
    """Plot vibration attenuation and modal suppression."""
    log.info("Generating vibration attenuation analysis...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # RMS over sliding windows
    ax = axes[0, 0]
    window_size = 1000
    rms_values = []
    timestamps = []
    for i in range(0, len(df) - window_size, window_size):
        rms = df['x_sensor'].iloc[i:i+window_size].std()
        rms_values.append(rms)
        timestamps.append(df['timestamp'].iloc[i + window_size//2])
    
    ax.plot(timestamps, rms_values, marker='o', markersize=3, linewidth=1.5, color='purple')
    ax.set_ylabel('RMS Vibration (m)', fontsize=11, fontweight='bold')
    ax.set_title('RMS Vibration Over Time (1000-point windows)', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Peak-to-peak variation
    ax = axes[0, 1]
    pp_values = []
    for i in range(0, len(df) - window_size, window_size):
        pp = df['x_sensor'].iloc[i:i+window_size].max() - df['x_sensor'].iloc[i:i+window_size].min()
        pp_values.append(pp)
    
    ax.plot(timestamps, pp_values, marker='s', markersize=3, linewidth=1.5, color='green')
    ax.set_ylabel('Peak-to-Peak Vibration (m)', fontsize=11, fontweight='bold')
    ax.set_title('Peak-to-Peak Amplitude Variation', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Vibration statistics
    ax = axes[1, 0]
    stats = {
        'Mean': df['x_sensor'].mean(),
        'Std Dev': df['x_sensor'].std(),
        'Min': df['x_sensor'].min(),
        'Max': df['x_sensor'].max(),
        'RMS': np.sqrt(np.mean(df['x_sensor']**2))
    }
    
    ax.axis('off')
    stat_text = "Vibration Statistics (Closed-Loop):\n\n"
    for key, value in stats.items():
        stat_text += f"{key:.<20} {value:.6e}\n"
    
    ax.text(0.1, 0.9, stat_text, transform=ax.transAxes, fontsize=11, verticalalignment='top',
            fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Control effort statistics
    ax = axes[1, 1]
    ctrl_stats = {
        'H∞ RMS': df['u_hinf'].std(),
        'H∞ Mean': df['u_hinf'].mean(),
        'Hybrid RMS': df['u_act_clamped'].std(),
        'Hybrid Mean': df['u_act_clamped'].mean(),
        'CNN RMS': df['u_cnn'].fillna(0).std(),
    }
    
    ax.axis('off')
    ctrl_text = "Control Signal Statistics:\n\n"
    for key, value in ctrl_stats.items():
        ctrl_text += f"{key:.<20} {value:.6f}\n"
    
    ax.text(0.1, 0.9, ctrl_text, transform=ax.transAxes, fontsize=11, verticalalignment='top',
            fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "vibration_attenuation_analysis.png", dpi=300, bbox_inches='tight')
    log.info(f"✓ Saved: output/vibration_attenuation_analysis.png")
    plt.close()

def plot_dynamic_stiffness(df, fs):
    """Plot effective dynamic stiffness comparison."""
    log.info("Generating dynamic stiffness analysis...")
    
    # Load pre-computed H∞ dynamic stiffness if available
    try:
        hinf_stiff = pd.read_csv(OUTPUT_DIR / "hinf_dynamic_stiffness.csv")
        has_hinf = len(hinf_stiff) > 0
    except:
        has_hinf = False
        log.warning("H∞ dynamic stiffness data not found")
    
    fig, axes = plt.subplots(1, 1, figsize=(12, 5))
    
    # Dynamic stiffness magnitude
    ax = axes
    if has_hinf and 'frequency' in hinf_stiff.columns:
        f_hinf = hinf_stiff['frequency'].values
        k_hinf = hinf_stiff['dynamic_stiffness'].values
        ax.semilogy(f_hinf, k_hinf, label='H∞ Dynamic Stiffness', linewidth=2, marker='o', markersize=4)
        
        # Mark modal frequencies
        for freq in MODAL_FREQUENCIES:
            if freq <= max(f_hinf):
                ax.axvline(freq, color='red', linestyle='--', alpha=0.5, linewidth=1.5)
                ax.text(freq, k_hinf.min() * 10, f'{freq}Hz', rotation=90, fontsize=9, color='red')
        
        ax.set_xlabel('Frequency (Hz)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Dynamic Stiffness (N/m)', fontsize=11, fontweight='bold')
        ax.set_title('Modal Dynamic Stiffness Response', fontsize=13, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, which='both')
    else:
        ax.text(0.5, 0.5, 'H∞ Dynamic Stiffness Data\nNot Available', 
                ha='center', va='center', transform=ax.transAxes, fontsize=14)
        ax.set_title('Modal Dynamic Stiffness Response (Data Not Available)', fontsize=13, fontweight='bold')
    
    plt.tight_layout()
    try:
        plt.savefig(OUTPUT_DIR / "dynamic_stiffness_analysis.png", dpi=300, bbox_inches='tight')
        log.info(f"✓ Saved: output/dynamic_stiffness_analysis.png")
    except Exception as e:
        log.warning(f"Could not save dynamic stiffness plot: {e}")
    finally:
        plt.close()

def generate_comparison_summary(df, fs):
    """Generate summary comparison table."""
    log.info("Generating comparison summary...")
    
    summary = {
        'Metric': [
            'Total Vibration (Std Dev)',
            'Vibration Mean',
            'Vibration RMS',
            'H∞ Control RMS',
            'Hybrid Control RMS',
            'CNN Contribution RMS',
            'Peak Vibration (m)',
            'Min Vibration (m)',
            'Max Control Signal (A)',
            'Sampling Rate (Hz)',
        ],
        'Value': [
            f"{df['x_sensor'].std():.6e}",
            f"{df['x_sensor'].mean():.6e}",
            f"{np.sqrt(np.mean(df['x_sensor']**2)):.6e}",
            f"{df['u_hinf'].std():.6f}",
            f"{df['u_act_clamped'].std():.6f}",
            f"{df['u_cnn'].fillna(0).std():.6f}",
            f"{df['x_sensor'].max():.6e}",
            f"{df['x_sensor'].min():.6e}",
            f"{df['u_act_clamped'].max():.6f}",
            f"{fs:.2f}",
        ]
    }
    
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(OUTPUT_DIR / "openloop_vs_closedloop_summary.csv", index=False)
    log.info(f"✓ Saved: output/openloop_vs_closedloop_summary.csv")
    
    print("\n" + "="*70)
    print("OPEN-LOOP VS CLOSED-LOOP SUMMARY")
    print("="*70)
    print(summary_df.to_string(index=False))
    print("="*70 + "\n")

def main():
    """Run all analyses."""
    log.info("="*70)
    log.info("Open-Loop vs Closed-Loop Analysis")
    log.info("="*70)
    
    df = load_data()
    fs = estimate_sampling_rate(df)
    
    # Generate plots
    plot_vibration_comparison(df, fs)
    plot_vibration_attenuation(df)
    plot_dynamic_stiffness(df, fs)
    generate_comparison_summary(df, fs)
    
    log.info("="*70)
    log.info("Open-Loop vs Closed-Loop Analysis Complete ✓")
    log.info("="*70)

if __name__ == "__main__":
    main()
