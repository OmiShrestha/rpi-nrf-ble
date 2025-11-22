# BLE & Bluetooth Mesh API - Raspberry Pi to nrf52 Series Controller

## Overview

This project provides two communication modes for controlling nRF52840 boards from a Raspberry Pi 5:

1. **BLE GATT Mode** - Point-to-point communication using Nordic UART Service (NUS)
2. **Bluetooth Mesh Mode** - Multi-node mesh network with provisioning and group communication

## Architecture

The codebase is organized into modular components:

### BLE GATT Components (Point-to-Point)
- `main.py` - Main entry point with interactive GATT command interface
- `ble_utils.py` - BLE connection, discovery, and command sending utilities
- `ble_device.py` - BLEDevice class for managing device state
- `notification_handler.py` - Handles incoming BLE notifications and data parsing
- `ble_manager.py` - Legacy compatibility wrapper (deprecated, use main.py)

### Bluetooth Mesh Components (Multi-Node Network)
- `mesh_main.py` - Interactive mesh provisioning and control interface
- `mesh_provisioner.py` - Bluetooth Mesh provisioner implementation
- `mesh_models.py` - Mesh model definitions (Generic OnOff, Level, Sensor, Config)
- `app.py` - Flask API with both GATT and Mesh endpoints

## Setup

1. **Activate Python environment and install dependencies:**
```bash
source ~/myenv/bin/activate
pip install bleak flask
```

2. **Verify bleak installation:**
```bash
python -m pip show bleak
```

3. **Ensure correct Python interpreter is selected in VS Code:**
   - Press `Ctrl+Shift+P`
   - Search for "Python: Select Interpreter"
   - Select `/home/raspberry/myenv/bin/python`

## Running the Applications

### Option 1: BLE GATT Mode (Point-to-Point)

For traditional point-to-point BLE communication using Nordic UART Service:

```bash
source ~/myenv/bin/activate
cd ~/Desktop/api
python main.py
```

**Interactive Commands:**
- `data` - View current device data received from notifications
- `history` - View notification history (last 20 notifications)
- `quit` - Exit the application

### Option 2: Bluetooth Mesh Mode (Multi-Node Network)

For Bluetooth Mesh provisioning and multi-node control:

```bash
source ~/myenv/bin/activate
cd ~/Desktop/api
python mesh_main.py
```

**Mesh Commands:**
- `onoff <address> <on|off>` - Send Generic OnOff command to node
- `level <address> <value>` - Send Generic Level command (-32768 to 32767)
- `sensor <address> [property_id]` - Query sensor data from node
- `list` - List all provisioned nodes
- `status` - Show mesh network status
- `quit` - Exit

**Example Usage:**
```
mesh> list
Provisioned Nodes:
  0x0002 - DART TARGETS-01 (connected)
  0x0003 - DART TARGETS-02 (connected)

mesh> onoff 0x0002 on
[MESH] Sending OnOff(On) to 0x0002...
[MESH] ✓ Command sent successfully

mesh> level 0x0003 16000
[MESH] Sending Level(16000) to 0x0003...
[MESH] ✓ Command sent successfully
```

### Option 3: Flask API Server

Run the Flask API server for remote control via HTTP:

```bash
source ~/myenv/bin/activate
cd ~/Desktop/api
python -c "from app import app; app.run(host='0.0.0.0', port=5000)"
```

## API Endpoints

### BLE GATT Endpoints (Point-to-Point)

- `POST /ble/discover` - Discover BLE devices
  ```json
  {"prefix": "DART TARGETS"}
  ```

- `POST /ble/send` - Send command via GATT
  ```json
  {"target_id": "01", "command": "status", "value": null}
  ```

- `GET /ble/data/<target_id>` - Get device data

- `POST /ble/disconnect/<target_id>` - Disconnect from device

### Bluetooth Mesh Endpoints

- `POST /mesh/scan` - Scan for unprovisioned mesh devices
  ```json
  {"prefix": "DART TARGETS", "timeout": 10.0}
  ```

- `POST /mesh/provision` - Provision device(s)
  ```json
  {"address": "AA:BB:CC:DD:EE:FF"}  // Optional: specific device
  // Or omit address to provision all discovered devices
  ```

- `POST /mesh/send` - Send mesh message
  ```json
  {
    "destination": "0x0002",
    "type": "onoff",
    "payload": {"on": true, "acknowledged": true}
  }
  ```
  
  Message types: `onoff`, `level`, `sensor`

- `GET /mesh/status` - Get mesh network status

- `GET /mesh/nodes` - List all provisioned nodes

## BLE Characteristics

The application uses the Nordic UART Service (NUS):
- **CMD_CHAR_UUID** (`6e400002-b5a3-f393-e0a9-e50e24dcca9e`) - Write commands to device
- **EVT_CHAR_UUID** (`6e400003-b5a3-f393-e0a9-e50e24dcca9e`) - Receive notifications from device

## Bluetooth Mesh Implementation

### Firmware Requirements

For your nRF52840 boards to work with the Raspberry Pi 5 provisioner, the firmware must:

1. **Advertise Mesh Provisioning Service**
   - Service UUID: `0x1827` (Mesh Provisioning Service)
   - Must be in unprovisioned device beacon advertisement

2. **Implement Mesh Provisioning GATT Characteristics**
   - Mesh Provisioning Data In: `0x2ADB`
   - Mesh Provisioning Data Out: `0x2ADC`

3. **Implement Mesh Proxy Service (After Provisioning)**
   - Service UUID: `0x1828` (Mesh Proxy Service)
   - Mesh Proxy Data In: `0x2ADD`
   - Mesh Proxy Data Out: `0x2ADE`

4. **Support Required Mesh Models**
   - Configuration Server (mandatory)
   - Generic OnOff Server (for on/off control)
   - Generic Level Server (for level control)
   - Sensor Server (for sensor data)

### Firmware Example Structure (C)

```c
// Include Bluetooth Mesh stack
#include <bluetooth/mesh.h>

// Define elements and models
static struct bt_mesh_model root_models[] = {
    BT_MESH_MODEL_CFG_SRV,
    BT_MESH_MODEL_GEN_ONOFF_SRV(&onoff_srv),
    BT_MESH_MODEL_GEN_LEVEL_SRV(&level_srv),
};

static struct bt_mesh_elem elements[] = {
    BT_MESH_ELEM(0, root_models, BT_MESH_MODEL_NONE),
};

static const struct bt_mesh_comp comp = {
    .cid = 0x05C3,  // Nordic Semiconductor Company ID
    .elem = elements,
    .elem_count = ARRAY_SIZE(elements),
};

// Provisioning support
static void prov_complete(uint16_t net_idx, uint16_t addr) {
    printk("Provisioning complete! Address: 0x%04x\n", addr);
}

static const struct bt_mesh_prov prov = {
    .uuid = dev_uuid,
    .complete = prov_complete,
};

// Initialize mesh in main()
void main(void) {
    bt_mesh_init(&prov, &comp);
    // Enable unprovisioned beacon
    bt_mesh_prov_enable(BT_MESH_PROV_ADV | BT_MESH_PROV_GATT);
}
```

### Zephyr SDK Configuration (prj.conf)

```ini
# Bluetooth configuration
CONFIG_BT=y
CONFIG_BT_OBSERVER=y
CONFIG_BT_PERIPHERAL=y
CONFIG_BT_GATT_CLIENT=y

# Bluetooth Mesh configuration
CONFIG_BT_MESH=y
CONFIG_BT_MESH_RELAY=y
CONFIG_BT_MESH_FRIEND=y
CONFIG_BT_MESH_GATT_PROXY=y
CONFIG_BT_MESH_PB_GATT=y
CONFIG_BT_MESH_PB_ADV=y

# Mesh models
CONFIG_BT_MESH_MODEL_EXTENSIONS=y
CONFIG_BT_MESH_GEN_ONOFF_SRV=y
CONFIG_BT_MESH_GEN_LEVEL_SRV=y
CONFIG_BT_MESH_SENSOR_SRV=y

# GATT configuration
CONFIG_BT_MESH_PROXY_USE_DEVICE_NAME=y
```

### How It Works

1. **Discovery Phase**
   - Raspberry Pi scans for BLE devices advertising Mesh Provisioning Service (0x1827)
   - Your nRF52840 boards must advertise this service when unprovisioned

2. **Provisioning Phase**
   - RPi connects to device via GATT
   - Exchanges provisioning data (network keys, unicast addresses)
   - Device joins the mesh network with assigned address

3. **Communication Phase**
   - After provisioning, devices expose Mesh Proxy Service (0x1828)
   - RPi can send mesh messages to any provisioned node
   - Messages are encrypted and relayed through the mesh network

4. **Multi-Node Control**
   - RPi can control multiple nRF boards simultaneously
   - Supports unicast (specific node), multicast (group), and broadcast addressing
   - Nodes can relay messages to extend network range

### Provisioning Flow

```
RPi (Provisioner)              nRF52840 (Unprovisioned Node)
      |                                    |
      |  1. Scan & Discover                |
      |<-----------------------------------|
      |     (Advertising 0x1827)           |
      |                                    |
      |  2. Connect via GATT               |
      |----------------------------------->|
      |                                    |
      |  3. Send Provisioning Invite       |
      |----------------------------------->|
      |                                    |
      |  4. Receive Capabilities           |
      |<-----------------------------------|
      |                                    |
      |  5. Exchange Keys & Address        |
      |<---------------------------------->|
      |                                    |
      |  6. Provisioning Complete          |
      |----------------------------------->|
      |                                    |
      |  7. Switch to Proxy Mode           |
      |     (Now using 0x1828)             |
      |                                    |
      |  8. Send Mesh Commands             |
      |----------------------------------->|
      |     (OnOff, Level, Sensor, etc.)   |
```

### Current Implementation Status

**Implemented:**
- ✅ Mesh network configuration and key management
- ✅ Device discovery and scanning
- ✅ Provisioning protocol structure
- ✅ Mesh model definitions (OnOff, Level, Sensor, Config)
- ✅ Mesh message encoding/decoding
- ✅ Interactive CLI and Flask API

**Requires Firmware Cooperation:**
- ⚠️ Full cryptographic provisioning (ECDH key exchange, AES-CCM encryption)
- ⚠️ Network layer encryption
- ⚠️ Transport layer segmentation
- ⚠️ Complete provisioning handshake

**Note:** This implementation provides the framework for Bluetooth Mesh. For production use, consider:
- Using a complete Bluetooth Mesh library like `python-bluetooth-mesh`
- Implementing full cryptographic operations
- Adding persistent storage for mesh configuration
- Supporting composition data parsing and model binding

## Known Issues & Solutions

### BLE GATT Issues

### Issue: No notifications received from board

**Problem:** Firmware sends responses via `mesh_send_private_message()` to address `0x0001`, which fails with error `-11` (no mesh connection).

**Solution:** Update firmware to send responses via Nordic UART TX instead of mesh:
```c
// Replace mesh send
// mesh_send_private_message(&chat, dest_addr, (const uint8_t *)odo_status);

// With UART TX send
bt_nus_send(NULL, (uint8_t *)odo_status, strlen(odo_status));
```

### Issue: "Unknown 'o' command" on firmware

**Problem:** Firmware expects exact 4 characters for `odo?`, but Python sends 5 characters (`odo?\n`).

**Solution:** Update firmware to accept newline terminator:
```c
if ((len == 4 && strncmp(data, "odo?", 4) == 0) ||
    (len == 5 && strncmp(data, "odo?\n", 5) == 0))
```

## Testing & Diagnostics

Several test scripts are included for debugging:
- `test_simple.py` - Basic command sending without mesh registration
- `test_formats.py` - Test different command formats
- `test_register.py` - Test mesh registration attempts
- `test_mesh.py` - Test both UART and Mesh Proxy characteristics
- `test_ble_chars.py` - List all BLE services and characteristics

Run tests with:
```bash
python test_simple.py
```

## Troubleshooting

### BLE GATT Mode
1. **Import errors for 'bleak':** Ensure correct Python environment is activated and selected in VS Code
2. **No devices found:** Verify board is powered on and advertising
3. **Connection timeouts:** Increase service discovery delay in `ble_utils.py`
4. **No notifications:** Check firmware is sending via UART TX, not mesh network

### Bluetooth Mesh Mode
1. **No unprovisioned devices found:** Ensure firmware advertises Mesh Provisioning Service (UUID 0x1827)
2. **Provisioning fails:** Check firmware implements provisioning GATT characteristics (0x2ADB, 0x2ADC)
3. **Cannot send mesh messages:** Verify firmware has Mesh Proxy Service (UUID 0x1828) enabled after provisioning
4. **Messages not received:** Ensure firmware implements required mesh models (Config Server, Generic OnOff, etc.)
5. **Cryptographic errors:** Full provisioning requires ECDH and AES-CCM - firmware must support these operations