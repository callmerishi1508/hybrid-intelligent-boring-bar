import argparse
import logging
import json
import sys
from pathlib import Path
import math

from config import configure_logging, CSV_SOURCES, DEFAULT_COLUMN_MAPPING, SIMULATION_SPEED_FACTOR, has_adt_credentials, has_iothub_connection
from telemetry_reader import TelemetryReader

try:
    from azure.identity import ClientSecretCredential
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.iot.device import IoTHubDeviceClient
    from twin_updater import TwinUpdater
except Exception:
    # Lazy imports so dry-run works without Azure SDKs installed
    ClientSecretCredential = None
    DigitalTwinsClient = None
    IoTHubDeviceClient = None
    TwinUpdater = None

log = logging.getLogger(__name__)


def _normalize_payload_value(value):
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        if hasattr(value, "dtype") and str(value.dtype).startswith("float"):
            if math.isnan(float(value)):
                return None
            return float(value)
    except Exception:
        pass
    return value


def parse_args():
    p = argparse.ArgumentParser(description="Stream CSV telemetry to IoT Hub and update Azure Digital Twin (dry-run supported)")
    p.add_argument("--source", default="merged", choices=["merged", "simscape", "u_cnn", "integrated_control"],
                   help="Choose a telemetry source or use merged project stream")
    p.add_argument("--dry-run", action="store_true", help="Do not call Azure services; just print payloads")
    p.add_argument("--max-rows", type=int, default=50)
    p.add_argument("--no-simulate", dest="simulate", action="store_false", help="Disable real-time simulation sleeps")
    p.add_argument("--speed", type=float, default=SIMULATION_SPEED_FACTOR)
    return p.parse_args()


def main():
    args = parse_args()
    configure_logging()

    if args.source == "merged":
        source_csv = [
            CSV_SOURCES["simscape"],
            CSV_SOURCES["u_cnn"],
            CSV_SOURCES["integrated_control"],
        ]
    else:
        source_csv = [CSV_SOURCES[args.source]]
    mapping = DEFAULT_COLUMN_MAPPING

    reader = TelemetryReader(source_csv, mapping)

    # Prepare ADT client if not dry-run
    adt_client = None
    iothub_client = None
    twin_updater = None
    if not args.dry_run:
        if ClientSecretCredential is None:
            log.error("Azure SDK imports failed. Install azure-identity and azure-digitaltwins-core")
            sys.exit(1)
        if not has_adt_credentials():
            log.error("ADT credentials missing in environment")
            sys.exit(1)
        cred = ClientSecretCredential(
            tenant_id=__import__('config').ADT_TENANT_ID,
            client_id=__import__('config').ADT_CLIENT_ID,
            client_secret=__import__('config').ADT_CLIENT_SECRET,
        )
        adt_client = DigitalTwinsClient(__import__('config').ADT_ENDPOINT, cred)
        twin_updater = TwinUpdater(adt_client)

        if has_iothub_connection():
            iothub_client = IoTHubDeviceClient.create_from_connection_string(__import__('config').IOTHUB_DEVICE_CONNECTION_STRING)

    print("Starting stream. dry-run=", args.dry_run)
    for i, row in enumerate(reader.stream(simulate_real_time=args.simulate, speed=args.speed, max_rows=args.max_rows)):
        # Build payload from normalized telemetry keys emitted by TelemetryReader
        payload = {
            "timestamp": _normalize_payload_value(row.get("timestamp")),
            "vibrationAmplitude": _normalize_payload_value(row.get("vibrationAmplitude")),
            "spindleSpeed": _normalize_payload_value(row.get("spindleSpeed")),
            "cnnOutput": _normalize_payload_value(row.get("cnnOutput")),
            "actuatorForce": _normalize_payload_value(row.get("actuatorForce")),
            "u_hinf": _normalize_payload_value(row.get("u_hinf")),
            "u_cnn": _normalize_payload_value(row.get("u_cnn")),
            "u_act": _normalize_payload_value(row.get("u_act")),
        }
        if args.dry_run or twin_updater is None:
            print(json.dumps(payload))
        else:
            # send telemetry to IoT Hub (device SDK)
            if iothub_client:
                try:
                    iothub_client.send_message(json.dumps(payload))
                except Exception:
                    log.exception("Failed to send IoT Hub message")
            # patch digital twin
            patch = [{"op": "replace", "path": "/telemetry/latest", "value": payload}]
            twin_updater.update_properties(__import__('config').DIGITAL_TWIN_ID, patch)

    if iothub_client:
        try:
            iothub_client.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
