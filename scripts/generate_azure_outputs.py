"""
Generate Azure-compatible telemetry JSONL and Digital Twin event packets,
plus visualization of telemetry stream synchronization and a dashboard mockup.
"""
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def _make_payload_row(row):
    return {
        "timestamp": float(row.get("timestamp", 0.0)),
        "vibrationAmplitude": float(row.get("x_sensor", 0.0)),
        "spindleSpeed": float(row.get("spindle_speed", np.nan)) if "spindle_speed" in row else 1200.0,
        "cnnCorrection": float(row.get("u_cnn", 0.0)),
        "actuatorForce": float(row.get("u_act_clamped", row.get("u_act", 0.0))),
        "mode2Residual": float(row.get("mode2_residual", 0.0)),
        "predictionConfidence": float(row.get("prediction_confidence", 0.9))
    }


def generate_telemetry_jsonl(integrated_csv_path: Path, out_jsonl: Path, max_rows=None):
    log.info(f"Loading integrated control CSV: {integrated_csv_path}")
    df = pd.read_csv(integrated_csv_path)
    if max_rows:
        df = df.head(max_rows)

    log.info(f"Writing telemetry JSONL to: {out_jsonl}")
    with open(out_jsonl, 'w', encoding='utf-8') as f:
        for _, row in df.iterrows():
            payload = _make_payload_row(row)
            f.write(json.dumps(payload) + '\n')

    log.info(f"Wrote {len(df)} telemetry records")


def generate_event_packets(df, out_events: Path):
    events = []
    # Detect high chatter windows and saturation to emit events
    saturated = df.get('u_act_clamped', df.get('u_act', 0)).abs() >= 3.95
    # Create saturation alerts
    sat_idxs = np.where(saturated)[0]
    for i in sat_idxs[::max(1, len(sat_idxs)//10)]:
        ts = float(df.iloc[i]['timestamp'])
        events.append({
            "timestamp": ts,
            "eventType": "saturation_alert",
            "details": {"u_act": float(df.iloc[i].get('u_act_clamped', df.iloc[i].get('u_act', 0))) }
        })

    # Chatter warnings (mode2 residual energy spikes)
    if 'mode2_residual' in df.columns:
        m2 = np.abs(df['mode2_residual'].fillna(0))
        thresh = np.percentile(m2, 95)
        high = np.where(m2 >= thresh)[0]
        for i in high[::max(1, len(high)//10)]:
            ts = float(df.iloc[i]['timestamp'])
            events.append({
                "timestamp": ts,
                "eventType": "chatter_warning",
                "details": {"mode2_residual": float(m2.iloc[i])}
            })

    # Predictive maintenance events (rare)
    pm_idx = int(len(df) * 0.9)
    if pm_idx < len(df):
        events.append({
            "timestamp": float(df.iloc[pm_idx]['timestamp']),
            "eventType": "predictive_maintenance",
            "details": {"score": 0.78, "recommendation": "Inspect spindle bearings"}
        })

    # Write events as JSONL
    log.info(f"Writing {len(events)} event packets to: {out_events}")
    with open(out_events, 'w', encoding='utf-8') as f:
        for e in events:
            f.write(json.dumps(e) + '\n')

    return events


def plot_cloud_sync_timeline(df, events, out_png: Path):
    # Simulate IoT Hub receive times with random small latency and occasional disconnect
    ts = df['timestamp'].to_numpy()
    base_time = datetime.now()
    receive_latency = np.clip(np.random.normal(0.15, 0.05, size=len(ts)), 0.02, 0.6)
    disconnect_mask = np.zeros(len(ts), dtype=bool)
    # simulate a disconnect between 40% and 45% of stream
    sidx = int(len(ts) * 0.40)
    eidx = int(len(ts) * 0.45)
    disconnect_mask[sidx:eidx] = True

    queued = np.cumsum(disconnect_mask.astype(int)) - np.cumsum(disconnect_mask.astype(int))
    # receive times: when disconnected, messages are queued and then flushed at reconnect
    recv_times = []
    cloud_times = []
    queued_counts = []
    queue_buf = []
    flush_points = []
    for i, t in enumerate(ts):
        if disconnect_mask[i]:
            # queued
            queue_buf.append(t)
            cloud_times.append(np.nan)
            recv_times.append(t + receive_latency[i])
        else:
            if queue_buf:
                # flush queued items now (simulate batch flush)
                flush_points.append((t, len(queue_buf)))
                queue_buf = []
            cloud_times.append(t + receive_latency[i])
            recv_times.append(t + receive_latency[i])
        queued_counts.append(len(queue_buf))

    fig, ax = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax[0].plot(ts, queued_counts, color='orange', label='Queued Telemetry Count')
    for t, cnt in flush_points:
        ax[0].axvline(t, color='red', linestyle='--', alpha=0.6)
        ax[0].text(t, max(queued_counts)*0.8, f'Flush {cnt}', rotation=90, color='red')
    ax[0].set_ylabel('Queued Messages', fontweight='bold')
    ax[0].legend()

    # plot latency histogram and sample cloud receive times overlay
    ax[1].plot(ts, receive_latency, color='blue', alpha=0.7, label='IoT Hub Latency (s)')
    ax[1].set_ylabel('Latency (s)', fontweight='bold')
    ax[1].set_xlabel('Time (s)', fontweight='bold')
    ax[1].legend()

    plt.suptitle('Edge → IoT Hub Synchronization and Disconnect/Recovery Simulation', fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    plt.close(fig)
    log.info(f"✓ Saved: {out_png}")


def plot_telemetry_stream(df, out_png: Path):
    fig, axes = plt.subplots(4, 1, figsize=(14, 8), sharex=True)
    axes[0].plot(df['timestamp'], df['x_sensor'], color='purple')
    axes[0].set_ylabel('Vibration Amplitude', fontweight='bold')
    axes[0].grid(True, alpha=0.3)

    # spindle speed (if not present use a synthetic line)
    if 'spindle_speed' in df.columns:
        axes[1].plot(df['timestamp'], df['spindle_speed'], color='brown')
    else:
        axes[1].plot(df['timestamp'], np.full(len(df), 1200.0), color='brown')
    axes[1].set_ylabel('Spindle Speed (RPM)', fontweight='bold')
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(df['timestamp'], df['u_cnn'].fillna(0), color='orange')
    axes[2].set_ylabel('CNN Correction (A)', fontweight='bold')
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(df['timestamp'], df.get('u_act_clamped', df.get('u_act', 0)), color='green')
    axes[3].set_ylabel('Actuator Current (A)', fontweight='bold')
    axes[3].set_xlabel('Time (s)', fontweight='bold')
    axes[3].grid(True, alpha=0.3)

    plt.suptitle('Telemetry Stream Visualization (Edge)', fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    plt.close(fig)
    log.info(f"✓ Saved: {out_png}")


def plot_dashboard_mockup(df, out_png: Path):
    # Simple dashboard mockup showing key KPIs
    latest = df.iloc[-1]
    vib = latest.get('x_sensor', 0.0)
    act = latest.get('u_act_clamped', latest.get('u_act', 0.0))
    cnn = latest.get('u_cnn', 0.0)

    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')

    # KPI boxes
    props = dict(boxstyle='round', facecolor='#f0f0f0', alpha=1.0)
    ax.text(0.05, 0.8, f'Chatter Severity: {np.abs(df.get("mode2_residual", pd.Series([0])).iloc[-1]):.4f}', fontsize=12, bbox=props)
    ax.text(0.05, 0.65, f'Vibration Level: {vib:.4e} m (RMS)', fontsize=12, bbox=props)
    ax.text(0.05, 0.5, f'Actuator Current: {act:.3f} A', fontsize=12, bbox=props)
    ax.text(0.05, 0.35, f'System Health: Good', fontsize=12, bbox=props)
    ax.text(0.05, 0.2, f'Predictive Maintenance: Due in 120 hrs', fontsize=12, bbox=props)

    # small plot snippets
    sub1 = fig.add_axes([0.55, 0.6, 0.4, 0.3])
    sub1.plot(df['timestamp'][-200:], df['x_sensor'][-200:], color='purple')
    sub1.set_title('Vibration (recent)')
    sub1.set_xticks([])

    sub2 = fig.add_axes([0.55, 0.25, 0.4, 0.3])
    sub2.plot(df['timestamp'][-200:], df.get('u_act_clamped', df.get('u_act', 0))[-200:], color='green')
    sub2.set_title('Actuator Current (recent)')
    sub2.set_xticks([])

    plt.suptitle('Digital Twin Dashboard Mockup', fontweight='bold')
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    plt.close(fig)
    log.info(f"✓ Saved: {out_png}")


def main():
    integrated_csv = OUTPUT_DIR / "integrated_control.csv"
    if not integrated_csv.exists():
        log.error("integrated_control.csv not found in output/ — run fuse_and_clamp.py first")
        return

    df = pd.read_csv(integrated_csv)

    # Telemetry JSONL
    telemetry_out = OUTPUT_DIR / "azure_telemetry.jsonl"
    events_out = OUTPUT_DIR / "digital_twin_events.jsonl"
    generate_telemetry_jsonl(integrated_csv, telemetry_out, max_rows=1000)

    # Event packets
    events = generate_event_packets(df, events_out)

    # Plots
    plot_cloud_sync_timeline(df, events, OUTPUT_DIR / "cloud_sync_timeline.png")
    plot_telemetry_stream(df, OUTPUT_DIR / "telemetry_stream_visualization.png")
    plot_dashboard_mockup(df, OUTPUT_DIR / "digital_twin_dashboard_mockup.png")

    log.info("Azure-compatible telemetry and event packets generated successfully")


if __name__ == '__main__':
    main()
