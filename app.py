from flask import Flask, request, jsonify
import asyncio
import time
from threading import Thread
from typing import Dict, Optional

# Import BLE modules for GATT-based communication
from ble_utils import discover_devices, ensure_connected, send_command as ble_send_command, disconnect_device
from ble_device import BLEDevice
from notification_handler import get_device_data, get_notification_history

# Import Bluetooth Mesh modules for mesh network communication
from mesh_provisioner import MeshProvisioner, MeshNetwork, MeshNode, discover_and_provision
from mesh_models import (
    GenericOnOffMessage, GenericLevelMessage, SensorMessage,
    create_onoff_command, create_level_command, create_sensor_query
)

app = Flask(__name__)

# Global state for BLE GATT devices (original functionality)
ble_devices: Dict[str, BLEDevice] = {}

# Global state for Bluetooth Mesh network
mesh_network: Optional[MeshNetwork] = None
mesh_provisioner: Optional[MeshProvisioner] = None

# Event loop for async operations
loop = None
loop_thread = None


def start_event_loop():
    """Start the asyncio event loop in a separate thread"""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()


def run_async(coro):
    """Run an async coroutine from sync context"""
    global loop
    if loop is None:
        return None
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)  # 30 second timeout


@app.before_first_request
def initialize():
    """Initialize the event loop on first request"""
    global loop_thread
    if loop_thread is None:
        loop_thread = Thread(target=start_event_loop, daemon=True)
        loop_thread.start()
        time.sleep(0.5)  # Give the loop time to start


@app.route('/')
def home():
    return jsonify({
        "status": "BLE & Mesh API is running",
        "modes": {
            "ble_gatt": "Point-to-point BLE GATT communication (Nordic UART Service)",
            "mesh": "Bluetooth Mesh network communication (multi-node)"
        },
        "endpoints": {
            "ble_gatt": ["/ble/discover", "/ble/send", "/ble/data", "/ble/disconnect"],
            "mesh": ["/mesh/scan", "/mesh/provision", "/mesh/send", "/mesh/status", "/mesh/nodes"]
        }
    })


# ============================================================================
# BLE GATT Endpoints (Original functionality - Nordic UART Service)
# ============================================================================

@app.route('/ble/discover', methods=['POST'])
def ble_discover():
    """Discover BLE devices using GATT"""
    try:
        data = request.get_json() or {}
        prefix = data.get('prefix', 'DART TARGETS')
        
        run_async(discover_devices(ble_devices, prefix))
        
        devices_info = {
            tid: {"address": dev.address, "connected": dev.connected}
            for tid, dev in ble_devices.items()
        }
        
        return jsonify({
            "status": "success",
            "devices": devices_info,
            "count": len(ble_devices)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/ble/send', methods=['POST'])
def ble_send():
    """Send command to BLE device via GATT (Nordic UART Service)"""
    try:
        data = request.get_json()
        target_id = data.get('target_id')
        command = data.get('command')
        value = data.get('value')
        
        if not target_id or not command:
            return jsonify({"error": "target_id and command required"}), 400
        
        run_async(ble_send_command(target_id, command, value, ble_devices))
        
        return jsonify({
            "status": "success",
            "target_id": target_id,
            "command": command,
            "value": value,
            "timestamp": time.time()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/ble/data/<target_id>', methods=['GET'])
def ble_get_data(target_id):
    """Get latest data from BLE device"""
    try:
        data = get_device_data(target_id, ble_devices)
        if data is None:
            return jsonify({"error": "Device not found"}), 404
        
        device = ble_devices[target_id]
        return jsonify({
            "target_id": target_id,
            "connected": device.connected,
            "data": data,
            "last_voltage": device.last_voltage,
            "last_notification": device.last_notification
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/ble/disconnect/<target_id>', methods=['POST'])
def ble_disconnect(target_id):
    """Disconnect from BLE device"""
    try:
        if target_id not in ble_devices:
            return jsonify({"error": "Device not found"}), 404
        
        device = ble_devices[target_id]
        run_async(disconnect_device(device))
        
        return jsonify({"status": "disconnected", "target_id": target_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Bluetooth Mesh Endpoints (New functionality)
# ============================================================================

@app.route('/mesh/scan', methods=['POST'])
def mesh_scan():
    """Scan for unprovisioned Bluetooth Mesh devices"""
    try:
        data = request.get_json() or {}
        prefix = data.get('prefix', 'DART TARGETS')
        timeout = data.get('timeout', 10.0)
        
        global mesh_network, mesh_provisioner
        
        if mesh_network is None:
            mesh_network = MeshNetwork("DART_Mesh_Network")
        
        if mesh_provisioner is None:
            mesh_provisioner = MeshProvisioner(mesh_network)
        
        unprovisioned = run_async(mesh_provisioner.scan_unprovisioned_devices(prefix, timeout))
        
        devices_info = [
            {"name": node.name, "address": node.address}
            for node in unprovisioned
        ]
        
        return jsonify({
            "status": "success",
            "unprovisioned_devices": devices_info,
            "count": len(devices_info)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/mesh/provision', methods=['POST'])
def mesh_provision():
    """Provision Bluetooth Mesh devices"""
    try:
        data = request.get_json() or {}
        device_address = data.get('address')  # Optional: provision specific device
        prefix = data.get('prefix', 'DART TARGETS')
        
        global mesh_network, mesh_provisioner
        
        if device_address:
            # Provision specific device
            if mesh_network is None:
                mesh_network = MeshNetwork("DART_Mesh_Network")
            if mesh_provisioner is None:
                mesh_provisioner = MeshProvisioner(mesh_network)
            
            # Scan for the specific device
            unprovisioned = run_async(mesh_provisioner.scan_unprovisioned_devices(prefix))
            target_node = next((n for n in unprovisioned if n.address == device_address), None)
            
            if not target_node:
                return jsonify({"error": "Device not found"}), 404
            
            success = run_async(mesh_provisioner.provision_device(target_node))
            
            return jsonify({
                "status": "success" if success else "failed",
                "device": {
                    "name": target_node.name,
                    "address": target_node.address,
                    "unicast_address": f"{target_node.unicast_address:#06x}" if target_node.unicast_address else None,
                    "provisioned": target_node.provisioned
                }
            })
        else:
            # Provision all available devices
            mesh_network = run_async(discover_and_provision(prefix))
            mesh_provisioner = MeshProvisioner(mesh_network)
            
            provisioned_devices = [
                {
                    "name": node.name,
                    "address": node.address,
                    "unicast_address": f"{node.unicast_address:#06x}" if node.unicast_address else None,
                    "provisioned": node.provisioned
                }
                for node in mesh_network.nodes.values()
            ]
            
            return jsonify({
                "status": "success",
                "network_name": mesh_network.network_name,
                "provisioned_devices": provisioned_devices,
                "count": len(provisioned_devices)
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/mesh/send', methods=['POST'])
def mesh_send():
    """Send message to Bluetooth Mesh node"""
    try:
        data = request.get_json()
        destination = data.get('destination')  # Unicast address (hex string or int)
        message_type = data.get('type', 'onoff')  # onoff, level, sensor
        payload = data.get('payload', {})
        
        if not destination:
            return jsonify({"error": "destination address required"}), 400
        
        if mesh_provisioner is None or mesh_network is None:
            return jsonify({"error": "Mesh network not initialized. Provision devices first."}), 400
        
        # Convert destination address
        if isinstance(destination, str):
            dest_addr = int(destination, 16)
        else:
            dest_addr = int(destination)
        
        # Create message based on type
        if message_type == 'onoff':
            on_off = payload.get('on', True)
            acknowledged = payload.get('acknowledged', True)
            message = create_onoff_command(on_off, acknowledged)
        elif message_type == 'level':
            level = payload.get('level', 0)
            message = create_level_command(level)
        elif message_type == 'sensor':
            property_id = payload.get('property_id')
            message = create_sensor_query(property_id)
        else:
            return jsonify({"error": f"Unknown message type: {message_type}"}), 400
        
        # Send message
        success = run_async(mesh_provisioner.send_mesh_message(dest_addr, message.opcode, message.payload))
        
        return jsonify({
            "status": "success" if success else "failed",
            "destination": f"{dest_addr:#06x}",
            "message_type": message_type,
            "payload": payload,
            "timestamp": time.time()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/mesh/status', methods=['GET'])
def mesh_status():
    """Get Bluetooth Mesh network status"""
    try:
        if mesh_network is None:
            return jsonify({
                "status": "not_initialized",
                "message": "Mesh network not initialized"
            })
        
        return jsonify({
            "status": "initialized",
            "network_name": mesh_network.network_name,
            "network_key_index": mesh_network.network_key_index,
            "app_key_index": mesh_network.app_key_index,
            "provisioner_address": f"{mesh_network.provisioner_address:#06x}",
            "next_unicast_address": f"{mesh_network.next_unicast_address:#06x}",
            "provisioned_nodes_count": len(mesh_network.nodes)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/mesh/nodes', methods=['GET'])
def mesh_nodes():
    """Get list of provisioned mesh nodes"""
    try:
        if mesh_network is None:
            return jsonify({"error": "Mesh network not initialized"}), 400
        
        nodes_info = [
            {
                "name": node.name,
                "ble_address": node.address,
                "unicast_address": f"{node.unicast_address:#06x}" if node.unicast_address else None,
                "provisioned": node.provisioned,
                "connected": node.client.is_connected if node.client else False,
                "elements_count": len(node.elements)
            }
            for node in mesh_network.nodes.values()
        ]
        
        return jsonify({
            "status": "success",
            "nodes": nodes_info,
            "count": len(nodes_info)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Run on all interfaces so it's accessible from internet
    app.run(host='0.0.0.0', port=5000, debug=True)
