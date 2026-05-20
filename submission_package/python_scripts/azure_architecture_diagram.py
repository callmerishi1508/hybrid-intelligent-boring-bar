"""
Generate a publication-quality Azure Digital Twin architecture diagram
specific to the hybrid H∞ + CNN smart machining system.

Saves: output/azure_architecture_diagram.png, .svg, .pdf at 300 DPI.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as mlines

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def box(ax, xy, w, h, label, fontsize=10, facecolor='#f7fbff', edgecolor='#0078D4'):
    rect = patches.FancyBboxPatch(xy, w, h,
                                  boxstyle='round,pad=0.3',
                                  linewidth=1.2,
                                  edgecolor=edgecolor,
                                  facecolor=facecolor)
    ax.add_patch(rect)
    ax.text(xy[0] + w/2, xy[1] + h/2, label, ha='center', va='center', fontsize=fontsize, weight='semibold')
    return rect


def small_box(ax, xy, w, h, label, fontsize=9, facecolor='white', edgecolor='#444444'):
    rect = patches.FancyBboxPatch(xy, w, h,
                                  boxstyle='round,pad=0.2',
                                  linewidth=0.9,
                                  edgecolor=edgecolor,
                                  facecolor=facecolor)
    ax.add_patch(rect)
    ax.text(xy[0] + w/2, xy[1] + h/2, label, ha='center', va='center', fontsize=fontsize)
    return rect


def draw_diagram():
    fig = plt.figure(figsize=(11.69, 8.27))  # A4 landscape
    ax = fig.add_subplot(111)
    ax.axis('off')

    # Layer headings
    ax.text(0.1, 0.92, 'Physical Layer', fontsize=12, weight='bold')
    ax.text(0.1, 0.72, 'Edge Control Layer', fontsize=12, weight='bold')
    ax.text(0.1, 0.48, 'Telemetry Layer', fontsize=12, weight='bold')
    ax.text(0.55, 0.72, 'Cloud Layer', fontsize=12, weight='bold')
    ax.text(0.55, 0.48, 'Monitoring Layer', fontsize=12, weight='bold')

    # Physical Layer box
    phys = small_box(ax, (0.05, 0.82), 0.28, 0.08, 'Physical Machining System\n(Boring Bar / Simscape)')
    sensors = small_box(ax, (0.05, 0.75), 0.28, 0.06, 'Sensors & Signal Acquisition\nAccelerometer / Vibration')

    # Edge Control Layer group boxes
    edge_x = 0.05
    edge_y = 0.58
    edge_w = 0.42
    edge_h = 0.12
    edge_bg = patches.FancyBboxPatch((edge_x-0.01, edge_y-0.01), edge_w+0.02, edge_h+0.12,
                                     boxstyle='round,pad=0.3', linewidth=0.8, edgecolor='#cccccc', facecolor='#ffffff')
    ax.add_patch(edge_bg)
    ax.text(edge_x, edge_y+edge_h+0.06, 'Edge Control Layer', fontsize=10, color='#333333')

    hinf = small_box(ax, (edge_x+0.02, edge_y+0.06), 0.18, 0.06, 'H∞ Robust Controller')
    cnn = small_box(ax, (edge_x+0.22, edge_y+0.06), 0.18, 0.06, 'CNN Adaptive Compensation')
    fusion = small_box(ax, (edge_x+0.12, edge_y-0.02), 0.18, 0.05, 'Hybrid Fusion\n(u_hinf + u_cnn)')
    actuator = small_box(ax, (edge_x+0.5, edge_y+0.02), 0.18, 0.08, 'Actuator System\n(Piezo Active Damping)')

    # Telemetry Layer
    telemetry_bg = patches.FancyBboxPatch((0.05, 0.34), 0.42, 0.12, boxstyle='round,pad=0.3', linewidth=0.8, edgecolor='#cccccc', facecolor='#ffffff')
    ax.add_patch(telemetry_bg)
    ax.text(0.06, 0.45, 'Telemetry Layer', fontsize=10, color='#333333')
    edge_proc = small_box(ax, (0.07, 0.36), 0.26, 0.08, 'Edge Telemetry Processing\n(real-time packaging / buffering)')
    buffer_box = small_box(ax, (0.34, 0.36), 0.12, 0.08, 'Local Buffering\n(disconnect handling)')

    # Cloud Layer boxes
    cloud_x = 0.5
    cloud_y = 0.58
    cloud_w = 0.42
    cloud_h = 0.12
    cloud_bg = patches.FancyBboxPatch((cloud_x-0.01, cloud_y-0.01), cloud_w+0.02, cloud_h+0.12, boxstyle='round,pad=0.3', linewidth=0.8, edgecolor='#cccccc', facecolor='#ffffff')
    ax.add_patch(cloud_bg)
    ax.text(cloud_x, cloud_y+cloud_h+0.06, 'Cloud Layer', fontsize=10, color='#333333')

    iothub = small_box(ax, (cloud_x+0.02, cloud_y+0.06), 0.18, 0.06, 'Azure IoT Hub')
    adt = small_box(ax, (cloud_x+0.22, cloud_y+0.06), 0.18, 0.06, 'Azure Digital Twin\n(Machine State)')
    analytics = small_box(ax, (cloud_x+0.12, cloud_y-0.02), 0.18, 0.05, 'Cloud Analytics & Monitoring\n(Real-time & ML)')

    # Monitoring Layer
    monitor_bg = patches.FancyBboxPatch((0.5, 0.34), 0.42, 0.12, boxstyle='round,pad=0.3', linewidth=0.8, edgecolor='#cccccc', facecolor='#ffffff')
    ax.add_patch(monitor_bg)
    ax.text(0.51, 0.45, 'Monitoring Layer', fontsize=10, color='#333333')
    dashboard = small_box(ax, (0.52, 0.36), 0.28, 0.08, 'Dashboard / Predictive Maintenance\n(Chatter Alerts / Health Index)')

    # Layer separation lines
    ax.plot([0.48, 0.48], [0.25, 0.95], color='#e0e0e0', linewidth=1)

    # Arrows and telemetry labels
    def arrow(a, b, text=None, text_offset=(0, 0), color='#0078D4', lw=1.5, style='->'):
        ax.annotate('', xy=b, xytext=a, arrowprops=dict(arrowstyle=style, color=color, lw=lw))
        if text:
            mid = ((a[0]+b[0])/2 + text_offset[0], (a[1]+b[1])/2 + text_offset[1])
            ax.text(mid[0], mid[1], text, fontsize=9, color='#333333', ha='center', va='center')

    # Physical -> Edge arrows
    arrow((0.19, 0.82), (0.16, 0.7), text='vibrationAmplitude, spindleSpeed', text_offset=(0, -0.02))
    arrow((0.16, 0.7), (0.12, 0.6), text='raw telemetry')

    # Edge control loop arrow (local only)
    arrow((edge_x+0.03, edge_y+0.12), (edge_x+0.03, edge_y+0.28), text='Local control loop (10 kHz)\nH∞ + CNN', color='#2b8cbe')
    # from fusion to actuator
    arrow((edge_x+0.3, edge_y+0.02), (edge_x+0.5, edge_y+0.06), text='u_act (command)')

    # Edge Telemetry -> IoT Hub with buffering
    arrow((0.34, 0.44), (0.52, 0.7), text='telemetry (vibrationAmplitude, cnnCorrection, actuatorCurrent)', text_offset=(0.1, 0))
    # local buffering shown
    arrow((0.4, 0.44), (0.4, 0.66), text='buffer / queue (on disconnect)', color='#ff7f00')

    # IoT Hub -> ADT -> Analytics -> Dashboard
    arrow((cloud_x+0.08, cloud_y+0.12), (cloud_x+0.28, cloud_y+0.12), text='twin update (state sync)')
    arrow((cloud_x+0.3, cloud_y+0.06), (cloud_x+0.2, cloud_y-0.02), text='telemetry → analytics')
    arrow((cloud_x+0.2, cloud_y-0.02), (0.7, 0.46), text='alerts / events', color='#d62728')

    # Event generation arrows
    ax.text(0.72, 0.62, 'Event generation:', fontsize=9, weight='bold')
    ax.text(0.72, 0.58, '- Chatter alerts', fontsize=9)
    ax.text(0.72, 0.54, '- Actuator saturation warnings', fontsize=9)
    ax.text(0.72, 0.50, '- Predictive maintenance', fontsize=9)

    # Cloud disconnect handling note
    ax.text(0.12, 0.32, 'Cloud Disconnect Handling: local buffer persists telemetry; on reconnect flushes to IoT Hub', fontsize=8, color='#555555')

    # Footnotes: Edge autonomy
    ax.text(0.05, 0.08, 'Edge Control Layer: H∞ controller enforces stability locally. CNN provides adaptive residual compensation. Control does NOT depend on cloud connectivity.', fontsize=8, color='#333333')

    # Title
    ax.set_title('Azure Digital Twin Architecture — Hybrid H∞ + CNN Smart Machining', fontsize=14, weight='bold')

    # Save outputs
    out_png = OUTPUT_DIR / 'azure_architecture_diagram.png'
    out_svg = OUTPUT_DIR / 'azure_architecture_diagram.svg'
    out_pdf = OUTPUT_DIR / 'azure_architecture_diagram.pdf'
    fig.savefig(out_png, dpi=300, bbox_inches='tight', facecolor='white')
    fig.savefig(out_svg, dpi=300, bbox_inches='tight', facecolor='white')
    fig.savefig(out_pdf, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"Saved: {out_png}")
    print(f"Saved: {out_svg}")
    print(f"Saved: {out_pdf}")


if __name__ == '__main__':
    draw_diagram()
