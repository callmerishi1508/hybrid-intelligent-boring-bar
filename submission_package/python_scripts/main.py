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
    p.add_argument("--live", action="store_true", help="Enable live updates to Azure Digital Twin and IoT Hub (requires credentials)")
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

    # Prepare ADT client if live mode enabled (and not dry-run)
    adt_client = None
    iothub_client = None
    twin_updater = None
    mode_label = "dry-run"
    
    if args.live and not args.dry_run:
        mode_label = "live"
        if ClientSecretCredential is None:
            log.error("Azure SDK imports failed. Install azure-identity and azure-digitaltwins-core")
            sys.exit(1)
        # Validate credentials using new helper
        from config import ensure_live_credentials
        success, error_msg = ensure_live_credentials()
        if not success:
            log.error(error_msg)
            sys.exit(1)
        
        try:
            cred = ClientSecretCredential(
                tenant_id=__import__('config').ADT_TENANT_ID,
                client_id=__import__('config').ADT_CLIENT_ID,
                client_secret=__import__('config').ADT_CLIENT_SECRET,
            )
            adt_client = DigitalTwinsClient(__import__('config').ADT_ENDPOINT, cred)
            twin_updater = TwinUpdater(adt_client)
            log.info("Azure Digital Twins client initialized")
        except Exception as e:
            log.error(f"Failed to initialize Azure clients: {e}")
            sys.exit(1)

        if __import__('config').has_iothub_connection():
            try:
                iothub_client = IoTHubDeviceClient.create_from_connection_string(__import__('config').IOTHUB_DEVICE_CONNECTION_STRING)
                log.info("IoT Hub device client initialized")
            except Exception as e:
                log.warning(f"Failed to initialize IoT Hub client: {e}")

    print(f"Starting stream. mode={mode_label}, max_rows={args.max_rows}, speed={args.speed}x")
    success_count = 0
    error_count = 0
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
        
        if not args.live or args.dry_run or twin_updater is None:
            # Dry-run: print payloads
            print(json.dumps(payload))
        else:
            # Live mode: send to Azure
            msg_sent = False
            twin_updated = False
            
            # Send telemetry to IoT Hub
            if iothub_client:
                try:
                    iothub_client.send_message(json.dumps(payload))
                    msg_sent = True
                except Exception as ex:
                    log.warning(f"Failed to send IoT Hub message: {ex}")
            
            # Patch digital twin properties (patch each property individually for flexibility)
            if twin_updater:
                patch = [
                    {"op": "replace", "path": "/vibrationAmplitude", "value": payload.get("vibrationAmplitude")},
                    {"op": "replace", "path": "/cnnOutput", "value": payload.get("cnnOutput")},
                    {"op": "replace", "path": "/actuatorForce", "value": payload.get("actuatorForce")},
                    {"op": "replace", "path": "/u_hinf", "value": payload.get("u_hinf")},
                    {"op": "replace", "path": "/u_cnn", "value": payload.get("u_cnn")},
                    {"op": "replace", "path": "/u_act", "value": payload.get("u_act")},
                ]
                twin_updated = twin_updater.update_properties(__import__('config').DIGITAL_TWIN_ID, patch)
            
            if msg_sent or twin_updated:
                success_count += 1
            else:
                error_count += 1
                
            if (success_count + error_count) % 10 == 0:
                log.info(f"Telemetry updates: {success_count} successful, {error_count} failed")

    if iothub_client:
        try:
            iothub_client.shutdown()
            log.info("IoT Hub client closed")
        except Exception:
            pass
    
    print(f"Stream finished. Total updates: {success_count} successful, {error_count} failed")

if __name__ == "__main__":
    main()
