# Azure DT Integration Setup

1. Create a `.env` file in project root with the following keys:

IOTHUB_DEVICE_CONNECTION_STRING=""
ADT_ENDPOINT="https://<your-instance>.api.<region>.digitaltwins.azure.net"
ADT_TENANT_ID="<tenant-id>"
ADT_CLIENT_ID="<client-id>"
ADT_CLIENT_SECRET="<client-secret>"
DIGITAL_TWIN_ID="<twin-id>"

2. Install Python dependencies

python -m pip install -r requirements.txt

3. Dry-run streaming

python main.py --dry-run --max-rows 20

4. Live run (requires credentials)

python main.py --max-rows 200

5. Troubleshooting
- If Azure SDK imports fail in live mode, ensure `azure-identity` and `azure-digitaltwins-core` are installed and you set ADT env vars.
- IoT Hub device SDK requires a device connection string; ensure `IOTHUB_DEVICE_CONNECTION_STRING` is set if you desire IoT Hub telemetry.
