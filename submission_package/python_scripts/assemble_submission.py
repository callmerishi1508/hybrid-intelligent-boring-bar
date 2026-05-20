"""
Assemble a submission package directory containing the project files,
datasets, outputs, documentation, and README for academic submission.

Creates: submission_package/ with structured folders.
"""
import os
import shutil
from pathlib import Path
import glob
import textwrap

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'submission_package'


def ensure_dirs():
    folders = [
        'simulink_models', 'matlab_scripts', 'python_scripts', 'datasets',
        'output_plots', 'azure_outputs', 'reports', 'documentation'
    ]
    for f in folders:
        (OUT / f).mkdir(parents=True, exist_ok=True)


def copy_files():
    # Simulink models
    for f in glob.glob(str(ROOT / '*.slx')):
        shutil.copy2(f, OUT / 'simulink_models')

    # MATLAB scripts
    for f in glob.glob(str(ROOT / '*.m')):
        shutil.copy2(f, OUT / 'matlab_scripts')

    # Python scripts
    for f in glob.glob(str(ROOT / 'scripts' / '*.py')):
        shutil.copy2(f, OUT / 'python_scripts')
    for f in glob.glob(str(ROOT / '*.py')):
        shutil.copy2(f, OUT / 'python_scripts')

    # Datasets (from output/datasets)
    ds_dir = ROOT / 'output' / 'datasets'
    if ds_dir.exists():
        for f in ds_dir.glob('*'):
            shutil.copy2(f, OUT / 'datasets')

    # Output plots (selected)
    out = ROOT / 'output'
    plot_exts = ['*.png', '*.svg', '*.pdf']
    for ext in plot_exts:
        for f in out.glob(ext):
            shutil.copy2(f, OUT / 'output_plots')

    # Azure outputs
    for name in ['azure_telemetry.jsonl', 'digital_twin_events.jsonl', 'cloud_sync_timeline.png', 'digital_twin_dashboard_mockup.png']:
        src = out / name
        if src.exists():
            shutil.copy2(src, OUT / 'azure_outputs')

    # Reports
    for name in ['FINAL_VALIDATION_REPORT.txt', 'validation_report.json', 'openloop_vs_closedloop_summary.csv', 'cnn_performance_metrics.csv']:
        src = out / name
        if src.exists():
            shutil.copy2(src, OUT / 'reports')

    # Documentation and architecture
    arch = out / 'azure_architecture_diagram.pdf'
    if arch.exists():
        shutil.copy2(arch, OUT / 'documentation')

    # README
    if (ROOT / 'README.md').exists():
        shutil.copy2(ROOT / 'README.md', OUT)


def create_readme_pdf():
    # Create a simple PDF summary from README.md using matplotlib text rendering
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return

    readme = (ROOT / 'README.md').read_text()
    lines = textwrap.wrap(readme, width=100)
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.01, 0.99, '\n'.join(lines), ha='left', va='top', fontsize=8, family='monospace')
    pdf_path = OUT / 'README.pdf'
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)


def make_zip():
    zip_path = ROOT / 'submission_package.zip'
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix('')), 'zip', OUT)
    print('Created zip:', zip_path)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    ensure_dirs()
    copy_files()
    create_readme_pdf()
    make_zip()
    print('Submission package assembled at', OUT)


if __name__ == '__main__':
    main()
