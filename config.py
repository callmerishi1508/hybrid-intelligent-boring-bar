import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

log = logging.getLogger(__name__)

# IoT Hub device connection string (optional)
IOTHUB_DEVICE_CONNECTION_STRING = os.environ.get("IOTHUB_DEVICE_CONNECTION_STRING", "").strip()

# Azure Digital Twins
ADT_ENDPOINT = os.environ.get("ADT_ENDPOINT", "").strip()  # e.g. "https://<your-instance>.api.wus2.digitaltwins.azure.net"
ADT_TENANT_ID = os.environ.get("ADT_TENANT_ID", "").strip()
ADT_CLIENT_ID = os.environ.get("ADT_CLIENT_ID", "").strip()
ADT_CLIENT_SECRET = os.environ.get("ADT_CLIENT_SECRET", "").strip()

# Digital Twin ID
DIGITAL_TWIN_ID = os.environ.get("DIGITAL_TWIN_ID", "").strip()

# Simulation speed factor (1.0 = real time). Can be overridden in CLI.
SIMULATION_SPEED_FACTOR = float(os.environ.get("SIMULATION_SPEED_FACTOR", "1.0"))

# Default CSV sources (relative to project root)
CSV_SOURCES = {
    "simscape": "output/simscape_export_clean.csv",
    "integrated_control": "output/integrated_control.csv",
    "u_cnn": "output/u_cnn_timeseries.csv",
}

# Default mapping from CSV columns to twin properties / telemetry fields.
DEFAULT_COLUMN_MAPPING = {
    "timestamp": "timestamp",
    "vibrationAmplitude": "x_sensor",
    "spindleSpeed": "spindleSpeed",
    "cnnOutput": "u_cnn",
    "actuatorForce": "u_act",
    "u_hinf": "u_hinf",
    "u_cnn": "u_cnn",
    "u_act": "u_act",
}

# Logging default
def configure_logging(level: str = None):
    level = level or os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("tensorflow").setLevel(logging.WARNING)

# Helper to check credentials presence
def has_iothub_connection():
    return bool(IOTHUB_DEVICE_CONNECTION_STRING)

def has_adt_credentials():
    return bool(ADT_ENDPOINT and (ADT_CLIENT_ID and ADT_CLIENT_SECRET))

if __name__ == "__main__":
    configure_logging("DEBUG")
    log.info("IOTHUB connection string present: %s", bool(IOTHUB_DEVICE_CONNECTION_STRING))
    log.info("ADT endpoint present: %s", bool(ADT_ENDPOINT))
    log.info("Digital twin id: %s", DIGITAL_TWIN_ID or "<not set>")
