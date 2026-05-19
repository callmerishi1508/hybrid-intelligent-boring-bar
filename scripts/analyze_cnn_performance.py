"""
CNN Performance Analysis
Analyze CNN contribution to hybrid control and compare with H∞ only behavior.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")

def load_data():
    """Load and merge all telemetry and control data."""
    log.info("Loading telemetry data...")
    
    simscape = pd.read_csv(OUTPUT_DIR / "simscape_export_clean.csv")
    integrated = pd.read_csv(OUTPUT_DIR / "integrated_control.csv")
    u_cnn_ts = pd.read_csv(OUTPUT_DIR / "u_cnn_timeseries.csv")
    
    # Merge on timestamp
    merged = pd.merge_asof(
        simscape[["timestamp", "x_sensor", "u_hinf"]],
        integrated[["timestamp", "u_cnn", "u_act", "u_act_clamped"]],
        on="timestamp",
        direction="nearest",
        tolerance=1e-4
    )
    
    log.info(f"Loaded {len(merged)} merged telemetry points")
    return merged

def compute_metrics(df):
    """Compute key performance metrics."""
    log.info("Computing performance metrics...")
    
    metrics = {}
    
    # Vibration metrics
    metrics['vibration_rms_open'] = df['x_sensor'].std()  # Open-loop approximation
    metrics['vibration_rms_closed'] = df['x_sensor'].std()  # Actual closed-loop
    
    # Control energy
    metrics['energy_hinf'] = (df['u_hinf'] ** 2).sum()
    metrics['energy_cnn'] = (df['u_cnn'].fillna(0) ** 2).sum()
    metrics['energy_hybrid'] = (df['u_act_clamped'] ** 2).sum()
    
    # Vibration reduction estimate
    metrics['vibration_reduction_pct'] = 0  # Will be computed with proper baseline
    
    # Control effort comparison
    metrics['hinf_rms'] = df['u_hinf'].std()
    metrics['cnn_rms'] = df['u_cnn'].fillna(0).std()
    metrics['hybrid_rms'] = df['u_act_clamped'].std()
    
    # CNN contribution
    metrics['cnn_contribution_pct'] = (metrics['energy_cnn'] / (metrics['energy_hinf'] + 1e-10)) * 100
    
    # Actuator saturation
    clamped_mask = (df['u_act_clamped'].abs() >= 3.9)
    metrics['saturation_events'] = clamped_mask.sum()
    metrics['saturation_pct'] = (clamped_mask.sum() / len(df)) * 100
    
    return metrics

def plot_cnn_contribution(df):
    """Plot CNN correction signal over time."""
    log.info("Generating CNN contribution plot...")
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    
    # Plot 1: H∞ vs CNN signals
    ax = axes[0]
    ax.plot(df['timestamp'], df['u_hinf'], label='H∞ Control', linewidth=1.5, alpha=0.8)
    ax.plot(df['timestamp'], df['u_cnn'].fillna(0), label='CNN Correction', linewidth=1, alpha=0.7)
    ax.set_ylabel('Control Signal (A)', fontsize=11, fontweight='bold')
    ax.set_title('H∞ Controller vs CNN Adaptive Correction', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Hybrid actuator command
    ax = axes[1]
    ax.plot(df['timestamp'], df['u_act'], label='Hybrid u_act (before clamp)', linewidth=1.5, alpha=0.8, color='green')
    ax.plot(df['timestamp'], df['u_act_clamped'], label='Hybrid u_act_clamped (actual)', linewidth=1, alpha=0.7, color='darkgreen')
    ax.axhline(y=4.0, color='r', linestyle='--', linewidth=1, label='Saturation limit (±4A)')
    ax.axhline(y=-4.0, color='r', linestyle='--', linewidth=1)
    ax.set_ylabel('Actuator Current (A)', fontsize=11, fontweight='bold')
    ax.set_title('Hybrid Actuator Command with Saturation', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Vibration response
    ax = axes[2]
    ax.plot(df['timestamp'], df['x_sensor'], label='Vibration (closed-loop)', linewidth=1, alpha=0.8, color='purple')
    ax.set_ylabel('Vibration Amplitude (m)', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax.set_title('Vibration Response Under Hybrid Control', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "cnn_contribution_over_time.png", dpi=300, bbox_inches='tight')
    log.info(f"✓ Saved: output/cnn_contribution_over_time.png")
    plt.close()

def plot_control_effort_comparison(metrics):
    """Plot control effort comparison (energy and RMS)."""
    log.info("Generating control effort comparison plot...")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Energy comparison
    ax = axes[0]
    labels = ['H∞ Only', 'CNN Only', 'Hybrid (H∞+CNN)']
    energies = [metrics['energy_hinf'], metrics['energy_cnn'], metrics['energy_hybrid']]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    bars = ax.bar(labels, energies, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
    ax.set_ylabel('Total Control Energy (A²·s)', fontsize=11, fontweight='bold')
    ax.set_title('Total Control Energy Comparison', fontsize=13, fontweight='bold')
    ax.grid(True, axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bar, energy in zip(bars, energies):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{energy:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # RMS comparison
    ax = axes[1]
    rms_values = [metrics['hinf_rms'], metrics['cnn_rms'], metrics['hybrid_rms']]
    bars = ax.bar(labels, rms_values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
    ax.set_ylabel('RMS Control Signal (A)', fontsize=11, fontweight='bold')
    ax.set_title('RMS Control Effort Comparison', fontsize=13, fontweight='bold')
    ax.grid(True, axis='y', alpha=0.3)
    
    # Add value labels
    for bar, rms in zip(bars, rms_values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{rms:.4f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "control_effort_comparison.png", dpi=300, bbox_inches='tight')
    log.info(f"✓ Saved: output/control_effort_comparison.png")
    plt.close()

def plot_cnn_magnitude_distribution(df):
    """Plot distribution of CNN correction magnitudes."""
    log.info("Generating CNN magnitude distribution plot...")
    
    cnn_corrections = df['u_cnn'].fillna(0)
    cnn_abs = np.abs(cnn_corrections)
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Histogram
    ax = axes[0]
    ax.hist(cnn_abs, bins=100, color='#ff7f0e', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax.axvline(cnn_abs.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {cnn_abs.mean():.4f}')
    ax.axvline(cnn_abs.std(), color='green', linestyle='--', linewidth=2, label=f'Std: {cnn_abs.std():.4f}')
    ax.set_xlabel('Absolute CNN Correction Magnitude (A)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax.set_title('Distribution of CNN Correction Magnitudes', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Time series with statistics
    ax = axes[1]
    ax.plot(df['timestamp'], cnn_abs, label='|CNN Correction|', linewidth=1, alpha=0.7, color='#ff7f0e')
    ax.axhline(cnn_abs.mean(), color='red', linestyle='--', linewidth=1.5, label=f'Mean: {cnn_abs.mean():.4f}')
    ax.fill_between(df['timestamp'], 0, cnn_abs, alpha=0.3, color='#ff7f0e')
    ax.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Absolute CNN Correction (A)', fontsize=11, fontweight='bold')
    ax.set_title('CNN Correction Magnitude Over Time', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "cnn_magnitude_distribution.png", dpi=300, bbox_inches='tight')
    log.info(f"✓ Saved: output/cnn_magnitude_distribution.png")
    plt.close()

def generate_metrics_table(metrics):
    """Generate and save metrics comparison table."""
    log.info("Generating metrics table...")
    
    table_data = {
        'Metric': [
            'H∞ Control Energy (A²·s)',
            'CNN Control Energy (A²·s)',
            'Hybrid Control Energy (A²·s)',
            'H∞ RMS Signal (A)',
            'CNN RMS Signal (A)',
            'Hybrid RMS Signal (A)',
            'CNN Contribution (%)',
            'Actuator Saturation Events',
            'Saturation Percentage (%)',
        ],
        'Value': [
            f"{metrics['energy_hinf']:.2f}",
            f"{metrics['energy_cnn']:.2f}",
            f"{metrics['energy_hybrid']:.2f}",
            f"{metrics['hinf_rms']:.6f}",
            f"{metrics['cnn_rms']:.6f}",
            f"{metrics['hybrid_rms']:.6f}",
            f"{metrics['cnn_contribution_pct']:.2f}%",
            f"{metrics['saturation_events']:.0f}",
            f"{metrics['saturation_pct']:.2f}%",
        ]
    }
    
    metrics_df = pd.DataFrame(table_data)
    metrics_df.to_csv(OUTPUT_DIR / "cnn_performance_metrics.csv", index=False)
    log.info(f"✓ Saved: output/cnn_performance_metrics.csv")
    
    print("\n" + "="*70)
    print("CNN PERFORMANCE ANALYSIS METRICS")
    print("="*70)
    print(metrics_df.to_string(index=False))
    print("="*70 + "\n")

def plot_saturation_analysis(df):
    """Plot actuator saturation events and analysis."""
    log.info("Generating saturation analysis plot...")
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    
    # Plot 1: Control signal with saturation markers
    ax = axes[0]
    ax.plot(df['timestamp'], df['u_act'], label='Hybrid u_act (pre-clamp)', linewidth=1.5, alpha=0.8, color='blue')
    ax.plot(df['timestamp'], df['u_act_clamped'], label='Hybrid u_act (clamped)', linewidth=1, alpha=0.7, color='darkblue', linestyle='--')
    
    # Highlight saturation regions
    saturated = np.abs(df['u_act_clamped']) >= 3.95
    ax.fill_between(df['timestamp'], -5, 5, where=saturated, alpha=0.2, color='red', label='Saturation region')
    
    ax.axhline(y=4.0, color='red', linestyle='--', linewidth=2, label='±4A Limit')
    ax.axhline(y=-4.0, color='red', linestyle='--', linewidth=2)
    ax.set_ylabel('Actuator Current (A)', fontsize=11, fontweight='bold')
    ax.set_title('Actuator Saturation Analysis', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([-5, 5])
    
    # Plot 2: Saturation duration histogram
    ax = axes[1]
    saturated_mask = np.abs(df['u_act_clamped']) >= 3.95
    
    # Find continuous saturation periods
    sat_periods = []
    in_period = False
    period_start = 0
    for i, is_sat in enumerate(saturated_mask):
        if is_sat and not in_period:
            period_start = i
            in_period = True
        elif not is_sat and in_period:
            sat_periods.append(i - period_start)
            in_period = False
    if in_period:
        sat_periods.append(len(saturated_mask) - period_start)
    
    if sat_periods:
        ax.hist(sat_periods, bins=30, color='red', alpha=0.7, edgecolor='black', linewidth=1)
        ax.set_xlabel('Saturation Period Duration (samples)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax.set_title(f'Saturation Event Duration Distribution ({len(sat_periods)} events)', fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "saturation_analysis.png", dpi=300, bbox_inches='tight')
    log.info(f"✓ Saved: output/saturation_analysis.png")
    plt.close()

def main():
    """Run all analyses."""
    log.info("="*70)
    log.info("CNN Performance Analysis")
    log.info("="*70)
    
    df = load_data()
    metrics = compute_metrics(df)
    
    # Generate plots
    plot_cnn_contribution(df)
    plot_control_effort_comparison(metrics)
    plot_cnn_magnitude_distribution(df)
    plot_saturation_analysis(df)
    generate_metrics_table(metrics)
    
    log.info("="*70)
    log.info("CNN Performance Analysis Complete ✓")
    log.info("="*70)

if __name__ == "__main__":
    main()
