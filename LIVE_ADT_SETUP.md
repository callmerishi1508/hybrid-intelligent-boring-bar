# Live Azure Digital Twin Integration Setup

This guide enables real-time telemetry streaming and property updates to your existing Azure Digital Twin instance.

## Prerequisites

✓ **Azure Resources (existing):**
- Azure Digital Twin: `project7-digitaltwin`
- Azure IoT Hub: `project7-iothub`
- Device: `boringbar-edge-device`
- Twin ID: `BoringBar_01`
- DTDL Model: `dtmi:project7:boringbar;1`

✓ **Python Environment:**
- All Azure SDKs already in `requirements.txt`:
  - `azure-identity`
  - `azure-digitaltwins-core`
  - `azure-iot-device`

✓ **Telemetry Data:**
- CSV files in `output/`:
  - `simscape_export_clean.csv`
  - `integrated_control.csv`
  - `u_cnn_timeseries.csv`

## Environment Variable Setup (Windows PowerShell)

```powershell
# 1. Azure Digital Twins - Service Principal credentials
$env:ADT_ENDPOINT = "https://project7-digitaltwin.api.<region>.digitaltwins.azure.net"
$env:ADT_TENANT_ID = "<your-tenant-id>"
$env:ADT_CLIENT_ID = "<your-service-principal-client-id>"
$env:ADT_CLIENT_SECRET = "<your-service-principal-client-secret>"

# 2. Twin ID to update
$env:DIGITAL_TWIN_ID = "BoringBar_01"

# 3. IoT Hub device connection string (optional, for device telemetry)
$env:IOTHUB_DEVICE_CONNECTION_STRING = "HostName=project7-iothub.azure-devices.net;DeviceId=boringbar-edge-device;SharedAccessKey=<device-key>"

# 4. Simulation speed (1.0 = real time, 0.1 = 10x faster)
$env:SIMULATION_SPEED_FACTOR = "1.0"
```

### Where to find credentials:

1. **ADT_ENDPOINT**: Azure Portal → Digital Twins Instance → Overview → Host name
   - Format: `https://project7-digitaltwin.api.wus2.digitaltwins.azure.net`

2. **ADT_TENANT_ID, ADT_CLIENT_ID, ADT_CLIENT_SECRET**: 
   - Created service principal with "Azure Digital Twins Data Owner" role
   - Stored in Azure Key Vault or local secure config

3. **IOTHUB_DEVICE_CONNECTION_STRING**:
   - Azure Portal → IoT Hub → Devices → `boringbar-edge-device` → Connection string (primary)

## Run Modes

### Dry-Run Mode (Safe, Local Testing - Default)
Print telemetry payloads to console without calling Azure:

```powershell
python main.py --dry-run --max-rows 20
```

**Output:** JSON payloads printed to console. No Azure API calls.

---

### Live Mode (Real Azure Digital Twin Updates)

**Prerequisites:**
- All environment variables set (see above)
- Service principal has `Azure Digital Twins Data Owner` role on the ADT instance
- Network access to Azure endpoints

**Command:**
```powershell
python main.py --live --max-rows 50 --speed 1.0
```

**What happens:**
1. ✓ Telemetry messages sent to IoT Hub via device connection string
2. ✓ Digital Twin properties patched in real-time:
   - `vibrationAmplitude`
   - `cnnOutput`
   - `actuatorForce`
   - `u_hinf`
   - `u_cnn`
   - `u_act`
3. ✓ Timestamps simulated at real-time rate (adjustable with `--speed`)
4. ✓ Updates visible in **Azure Digital Twins Explorer** within seconds

---

## Verification Steps

### 1. Dry-Run Test (Local, No Azure)
```powershell
python main.py --dry-run --max-rows 10
```
✓ Should print JSON payloads
✓ No errors
✓ Takes ~1 second

---

### 2. Pre-Flight Check (Credentials Only)
```powershell
python -c "from config import ensure_live_credentials; success, msg = ensure_live_credentials(); print('OK' if success else f'FAIL: {msg}')"
```
✓ Should print: `OK`
✗ If fail: check environment variables

---

### 3. Live Test (First Run - Small Dataset)
```powershell
python main.py --live --max-rows 20 --speed 10.0
```
✓ Should print: `Starting stream. mode=live, max_rows=20, speed=10.0x`
✓ Progress logs: "Telemetry updates: X successful, Y failed"
✓ After completion: summary line
✗ If auth error: check service principal RBAC
✗ If network error: check firewall/proxy

---

### 4. Verify in Azure Digital Twins Explorer

1. Open **Azure Digital Twins Explorer** (Azure Portal or desktop app)
2. Navigate to `BoringBar_01` twin
3. Look for properties:
   - `vibrationAmplitude`: should show recent decimal value
   - `cnnOutput`: should show recent decimal value
   - `actuatorForce`: should show recent decimal value
   - Timestamps and fused control signals

**Expected Property View:**
```
BoringBar_01
├── vibrationAmplitude: 0.0234
├── cnnOutput: -0.001
├── actuatorForce: 0.002
├── u_hinf: 0.0015
├── u_cnn: -0.001
└── u_act: 0.0005
```

---

### 5. Monitor IoT Hub (Optional)

**Via Azure Portal:**
1. Azure Portal → IoT Hub → Monitoring → Metrics
2. Look for "Telemetry Messages" count increasing

**Via Azure CLI:**
```bash
az iot hub monitor-events -n project7-iothub -d boringbar-edge-device
```

---

## Rate Limiting & Throttling

Azure services apply throttling:
- **ADT updates**: ~1000 updates/min per instance (soft limit)
- **IoT Hub messages**: varies by tier

If hitting limits, use `--speed` to slow down:
```powershell
# 5x slower = 10 telemetry points/second instead of 50
python main.py --live --speed 0.2 --max-rows 1000
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Missing required environment variables" | Check all `ADT_*` and `DIGITAL_TWIN_ID` vars are set |
| "Failed to initialize Azure clients" | Verify service principal has `Azure Digital Twins Data Owner` role |
| "ADT update failed: 403" | RBAC issue; check service principal permissions |
| "ADT update failed: 404" | Twin `BoringBar_01` does not exist; check twin ID spelling |
| "ADT update failed: 429" | Rate limited; use `--speed 0.5` to slow down |
| IoT Hub messages not appearing | Check `IOTHUB_DEVICE_CONNECTION_STRING` is valid |
| Slow response times | Normal for simulation; use `--speed` to accelerate |

---

## Full Example Workflow

```powershell
# 1. Set environment variables
$env:ADT_ENDPOINT = "https://project7-digitaltwin.api.wus2.digitaltwins.azure.net"
$env:ADT_TENANT_ID = "12345678-1234-1234-1234-123456789012"
$env:ADT_CLIENT_ID = "87654321-4321-4321-4321-210987654321"
$env:ADT_CLIENT_SECRET = "abc...xyz"
$env:DIGITAL_TWIN_ID = "BoringBar_01"
$env:IOTHUB_DEVICE_CONNECTION_STRING = "HostName=...;DeviceId=...;SharedAccessKey=..."

# 2. Dry-run test (verify data)
python main.py --dry-run --max-rows 10

# 3. Credential check
python -c "from config import ensure_live_credentials; success, msg = ensure_live_credentials(); print('OK' if success else f'FAIL: {msg}')"

# 4. Live test with 50 rows, 10x speed
python main.py --live --max-rows 50 --speed 10.0

# 5. Verify in Azure Digital Twins Explorer
# (see "Verify in Azure Digital Twins Explorer" section above)

# 6. Full run (all data, real-time)
python main.py --live --speed 1.0
```

---

## Key Design Decisions

- **No new Azure infrastructure**: Uses existing ADT instance and IoT Hub
- **Simulation-only telemetry**: Data from CSVs, not physical sensors
- **Individual property patches**: Each property updated separately for robustness
- **Retry logic**: Transient errors (408, 429, 500, 503) automatically retry with backoff
- **Lightweight**: ~150 lines of integration code, minimal dependencies
- **Safe defaults**: `--dry-run` is the default; must explicitly use `--live` for Azure updates

---

## Next Steps

1. Set environment variables (see above)
2. Run dry-run test: `python main.py --dry-run --max-rows 10`
3. Verify credentials: `python -c "from config import ensure_live_credentials; ..."`
4. Run live test: `python main.py --live --max-rows 50`
5. Check Azure Digital Twins Explorer for updated properties
6. Commit changes to git (`.env` is in `.gitignore`, so credentials stay local)

---

**Questions?** Check the error logs with `LOG_LEVEL=DEBUG`:
```powershell
$env:LOG_LEVEL = "DEBUG"
python main.py --live --max-rows 10
```
