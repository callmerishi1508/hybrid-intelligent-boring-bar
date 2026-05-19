"""
run_all_analysis.py - Orchestrate all validation and analysis scripts
Generates comprehensive project validation evidence and presentation assets
"""

import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent

def run_script(script_name, description):
    """Run a Python script and handle errors."""
    log.info(f"\n{'='*80}")
    log.info(f"RUNNING: {description}")
    log.info(f"Script: {script_name}")
    log.info(f"{'='*80}")
    
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        log.error(f"Script not found: {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=SCRIPTS_DIR.parent,
            capture_output=False,
            check=True,
            timeout=300  # 5 minute timeout per script
        )
        log.info(f"✓ {description} COMPLETED")
        return True
    except subprocess.TimeoutExpired:
        log.error(f"✗ {description} TIMEOUT (>5 min)")
        return False
    except subprocess.CalledProcessError as e:
        log.error(f"✗ {description} FAILED (exit code {e.returncode})")
        return False
    except Exception as e:
        log.error(f"✗ {description} ERROR: {e}")
        return False

def main():
    """Run all analysis pipelines."""
    log.info("="*80)
    log.info("PROJECT 7 - FINAL VALIDATION & ANALYSIS PIPELINE")
    log.info("="*80)
    
    scripts = [
        ("analyze_cnn_performance.py", "CNN Performance Analysis"),
        ("analyze_openloop_vs_closedloop.py", "Open-Loop vs Closed-Loop Analysis"),
        ("generate_final_report.py", "Final Validation Report Generation"),
    ]
    
    results = {}
    for script, description in scripts:
        success = run_script(script, description)
        results[description] = success
    
    # Print summary
    log.info("\n" + "="*80)
    log.info("ANALYSIS PIPELINE SUMMARY")
    log.info("="*80)
    
    for desc, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        log.info(f"{status} - {desc}")
    
    total_passed = sum(1 for s in results.values() if s)
    total_scripts = len(results)
    
    log.info(f"\nTotal: {total_passed}/{total_scripts} completed successfully")
    
    if total_passed == total_scripts:
        log.info("\n✓ ALL ANALYSES COMPLETED SUCCESSFULLY")
        log.info("\nGenerated outputs:")
        log.info("  • output/cnn_performance_metrics.csv")
        log.info("  • output/cnn_contribution_over_time.png")
        log.info("  • output/control_effort_comparison.png")
        log.info("  • output/cnn_magnitude_distribution.png")
        log.info("  • output/saturation_analysis.png")
        log.info("  • output/openloop_vs_closedloop.png")
        log.info("  • output/vibration_attenuation_analysis.png")
        log.info("  • output/dynamic_stiffness_analysis.png")
        log.info("  • output/openloop_vs_closedloop_summary.csv")
        log.info("  • output/FINAL_VALIDATION_REPORT.txt")
        log.info("  • output/system_components_summary.csv")
        log.info("="*80)
        return 0
    else:
        log.error("\n✗ SOME ANALYSES FAILED - CHECK LOGS ABOVE")
        log.info("="*80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
