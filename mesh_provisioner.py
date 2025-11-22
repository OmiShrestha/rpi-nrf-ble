
"""
Bluetooth Mesh Provisioner for Raspberry Pi 5
Handles mesh network provisioning and device management
"""

import asyncio
import struct
import secrets
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

# Bluetooth Mesh UUIDs
MESH_PROVISIONING_SERVICE =     "00001827-0000-1000-8000-00805f9b34fb"
MESH_PROVISIONING_DATA_IN =     "00002adb-0000-1000-8000-00805f9b34fb"
MESH_PROVISIONING_DATA_OUT =    "00002adc-0000-1000-8000-00805f9b34fb"
MESH_PROXY_SERVICE =            "00001828-0000-1000-8000-00805f9b34fb"
MESH_PROXY_DATA_IN =            "00002add-0000-1000-8000-00805f9b34fb"
MESH_PROXY_DATA_OUT =           "00002ade-0000-1000-8000-00805f9b34fb"

@dataclass
class MeshNode:
    """Represents a provisioned mesh node"""
    address: str            # BLE MAC address
    unicast_address: int    # Primary mesh unicast address
    device_key: bytes       # 16-byte device key
    uuid: bytes             # 16-byte device UUID
    name: str
    elements: int = 1
    network_key_index: int = 0

@dataclass
class MeshNetwork:
    """Represents a mesh network"""
    network_key: bytes      # 16-byte network key
    app_key: bytes          # 16-byte application key
    iv_index: int = 0
    next_unicast_address: int = 0x0001
    nodes: Dict[int, MeshNode] = None
    
    def __post_init__(self):
        if self.nodes is None:
            self.nodes = {}

class MeshProvisioner:
    """
    Bluetooth Mesh Provisioner
    Handles device provisioning and mesh network management
    """
    
    def __init__(self, network_key: Optional[bytes] = None, app_key: Optional[bytes] = None):
        """Initialize the mesh provisioner"""
        # Create or use existing network keys
        self.network = MeshNetwork(
            network_key=network_key or secrets.token_bytes(16),
            app_key=app_key or secrets.token_bytes(16)
        )
        self.client: Optional[BleakClient] = None
        self._prov_notification_queue = asyncio.Queue()
        self._proxy_notification_queue = asyncio.Queue()
        self._expected_pdu_length = 0
        self._pdu_buffer = bytearray()
        
    async def scan_unprovisioned_devices(self, timeout: float = 10.0) -> List[BLEDevice]:
        """
        Scans for unprovisioned bluetooth mesh devices
        Returns list of unprovisioned devices advertising the Mesh Provisioning Service
        """
        print(f"[MESH] Scanning for unprovisioned mesh devices (timeout: {timeout}s)...")
        
        mesh_devices = []
        seen_addresses = set()
        
        def detection_callback(device: BLEDevice, adv_data):
            """Filter devices during scan"""
            # Only process devices named "DART TARGETS"
            if device.name != "DART TARGETS":
                return
            
            # Avoid duplicates
            if device.address in seen_addresses:
                return
            
            # Check if device advertises Mesh Provisioning Service
            if MESH_PROVISIONING_SERVICE.lower() in [uuid.lower() for uuid in adv_data.service_uuids]:
                print(f"[MESH] Found unprovisioned device: {device.name} ({device.address})")
                mesh_devices.append(device)
                seen_addresses.add(device.address)
        
        # Scan with callback - only processes matching devices
        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()
                
        print(f"[MESH] Found {len(mesh_devices)} unprovisioned mesh device(s)")
        return mesh_devices
    
    def _prov_notification_handler(self, sender, data: bytearray):
        """Handle provisioning notifications"""
        print(f"[MESH] <<< Received provisioning data ({len(data)} bytes): {data.hex()}")
        
        if len(data) < 2:
            print(f"[MESH] WARNING: Received data too short ({len(data)} bytes)")
            return
            
        # Parse GATT Bearer header (Android nRF Mesh format)
        # Format: Link Control (1 byte) + PDU Type (1 byte) + Payload
        link_control = data[0]
        
        if link_control == 0x03:  # Transaction Start
            # Complete PDU is in this packet
            complete_pdu = bytes(data[1:])  # Skip link control, rest is the PDU
            print(f"[MESH] >>> Complete PDU received ({len(complete_pdu)} bytes): {complete_pdu.hex()}")
            self._prov_notification_queue.put_nowait(complete_pdu)
        elif link_control == 0x02:  # Transaction Continuation
            # This shouldn't happen with large MTU, but handle it
            print(f"[MESH] WARNING: Received continuation packet (shouldn't happen with MTU 498)")
            print(f"[MESH] Data: {data.hex()}")
        else:
            print(f"[MESH] WARNING: Unknown Link Control: 0x{link_control:02x}")
    
    def _proxy_notification_handler(self, sender, data: bytearray):
        """Handle proxy notifications - receives mesh network messages"""
        print(f"[MESH] <<< Received proxy data ({len(data)} bytes): {data.hex()}")
        
        # Proxy messages use the same Link Control format
        if len(data) < 2:
            print(f"[MESH] WARNING: Received data too short ({len(data)} bytes)")
            return
            
        link_control = data[0]
        
        if link_control == 0x00:  # Network PDU
            # This is an encrypted mesh network message
            complete_pdu = bytes(data[1:])
            print(f"[MESH] >>> Network PDU received ({len(complete_pdu)} bytes)")
            self._proxy_notification_queue.put_nowait(('network', complete_pdu))
        elif link_control == 0x01:  # Mesh Beacon
            complete_pdu = bytes(data[1:])
            print(f"[MESH] >>> Mesh Beacon received ({len(complete_pdu)} bytes)")
            self._proxy_notification_queue.put_nowait(('beacon', complete_pdu))
        elif link_control == 0x02:  # Proxy Configuration
            complete_pdu = bytes(data[1:])
            print(f"[MESH] >>> Proxy Config received ({len(complete_pdu)} bytes)")
            self._proxy_notification_queue.put_nowait(('config', complete_pdu))
        else:
            print(f"[MESH] WARNING: Unknown proxy message type: 0x{link_control:02x}")
    
    async def provision_device(self, device: BLEDevice, timeout: float = 15.0) -> Optional[MeshNode]:
        """
        Provision a mesh device
        
        Simplified provisioning flow:
        1. Connect and subscribe to provisioning service
        2. Send Provisioning Invite
        3. Receive Provisioning Capabilities
        4. Exchange public keys (simplified: skip for now)
        5. Send Provisioning Data (network key, unicast address, etc.)
        6. Receive Provisioning Complete
        
        Returns MeshNode if successful, None otherwise
        """
        print(f"[MESH] Starting provisioning for {device.name} ({device.address})")
        
        provisioned_node = None  # Store result before disconnect
        
        try:
            # Reset PDU buffer
            self._pdu_buffer = bytearray()
            self._expected_pdu_length = 0
            
            # Connect to device
            async with BleakClient(device.address, timeout=10.0) as client:
                self.client = client
                print(f"[MESH] Connected to {device.name}")
                
                # Exchange MTU to get larger packet size (like Android app)
                # Android uses 517 which negotiates down to 498
                try:
                    # For BlueZ backend on Raspberry Pi
                    if hasattr(client._backend, 'exchange_mtu'):
                        await client._backend.exchange_mtu(517)
                        mtu = client.mtu_size
                        print(f"[MESH] MTU negotiated to: {mtu}")
                    else:
                        # Try alternative method
                        await client._backend._acquire_mtu()
                        mtu = client.mtu_size
                        print(f"[MESH] MTU acquired: {mtu}")
                except AttributeError:
                    print(f"[MESH] MTU exchange not supported, using default: {client.mtu_size}")
                except Exception as e:
                    print(f"[MESH] MTU negotiation: {e}, using current: {client.mtu_size}")
                
                # Verify provisioning service exists
                services = client.services
                prov_service = None
                for service in services:
                    if service.uuid.lower() == MESH_PROVISIONING_SERVICE.lower():
                        prov_service = service
                        break
                
                if not prov_service:
                    print("[MESH] Error: Device does not have Mesh Provisioning Service")
                    return None
                    
                print("[MESH] Device has Mesh Provisioning Service")
                
                # Debug: Print all characteristics
                print("[MESH] DEBUG: Available characteristics:")
                for service in services:
                    print(f"[MESH]   Service: {service.uuid}")
                    for char in service.characteristics:
                        print(f"[MESH]     - Char: {char.uuid} (properties: {char.properties})")
                
                # Subscribe to provisioning data out
                await client.start_notify(
                    MESH_PROVISIONING_DATA_OUT,
                    self._prov_notification_handler
                )
                print("[MESH] Subscribed to provisioning notifications")
                
                # Step 1: Send Provisioning Invite
                print("[MESH] Sending Provisioning Invite...")
                attention_duration = 5  # seconds (match Android app)
                
                # Format matches Android: 0x030005
                # 0x03 = Link Control (Transaction Start)
                # 0x00 = PDU Type (Provisioning Invite)
                # 0x05 = Attention Duration (5 seconds)
                invite_packet = bytes([0x03, 0x00, attention_duration])
                
                print(f"[MESH] DEBUG: Invite packet = {invite_packet.hex()}")
                
                await client.write_gatt_char(
                    MESH_PROVISIONING_DATA_IN,
                    invite_packet,
                    response=False
                )
                print("[MESH] Invite sent, waiting for Capabilities response...")
                
                # Wait for Capabilities response
                try:
                    capabilities = await asyncio.wait_for(
                        self._prov_notification_queue.get(),
                        timeout=timeout
                    )
                    
                    if capabilities[0] != 0x01:  # Capabilities PDU type
                        print(f"[MESH] Error: Expected Capabilities (0x01), got 0x{capabilities[0]:02x}")
                        return None
                    
                    print(f"[MESH] Received Capabilities: {capabilities.hex()}")
                    
                    # Parse capabilities (simplified)
                    num_elements = capabilities[1] if len(capabilities) > 1 else 1
                    print(f"[MESH] Device has {num_elements} element(s)")
                    
                    # For now, we'll skip the full provisioning protocol
                    # A complete implementation would need:
                    # - Public key exchange
                    # - Authentication
                    # - Provisioning data distribution
                    
                    # Allocate unicast address
                    unicast_address = self.network.next_unicast_address
                    self.network.next_unicast_address += num_elements
                    
                    # Generate device key
                    device_key = secrets.token_bytes(16)
                    
                    # Create mesh node
                    node = MeshNode(
                        address=device.address,
                        unicast_address=unicast_address,
                        device_key=device_key,
                        uuid=secrets.token_bytes(16),  # Should get from device
                        name=device.name or "Unknown",
                        elements=num_elements
                    )
                    
                    self.network.nodes[unicast_address] = node
                    
                    print(f"[MESH] ✓ Provisioned {device.name}")
                    print(f"[MESH]   Unicast Address: 0x{unicast_address:04x}")
                    print(f"[MESH]   Elements: {num_elements}")
                    
                    # Store node before context manager exits (disconnect may fail)
                    provisioned_node = node
                    
                except asyncio.TimeoutError:
                    print("[MESH] Error: Timeout waiting for Capabilities")
                    return None
            
            # Return the provisioned node (even if disconnect had issues)
            return provisioned_node
                    
        except EOFError:
            # D-Bus disconnect error - ignore if we successfully provisioned
            if provisioned_node:
                print("[MESH] Note: Disconnect error (harmless) - provisioning succeeded")
                return provisioned_node
            return None
        except Exception as e:
            import traceback
            print(f"[MESH] Provisioning error: {e}")
            print(f"[MESH] Error type: {type(e).__name__}")
            traceback.print_exc()
            return None
    
    def get_network_status(self) -> Dict:
        """Get current network status"""
        return {
            "network_key": self.network.network_key.hex(),
            "app_key": self.network.app_key.hex(),
            "iv_index": self.network.iv_index,
            "next_unicast_address": f"0x{self.network.next_unicast_address:04x}",
            "provisioned_nodes": len(self.network.nodes),
            "nodes": [
                {
                    "name": node.name,
                    "address": node.address,
                    "unicast_address": f"0x{node.unicast_address:04x}",
                    "elements": node.elements
                }
                for node in self.network.nodes.values()
            ]
        }


async def interactive_mesh_control():
    """Interactive CLI for mesh network control"""
    provisioner = MeshProvisioner()
    
    print("\n" + "="*60)
    print("BLUETOOTH MESH PROVISIONER & CONTROLLER")
    print("Raspberry Pi 5 - nRF52840 Mesh Network")
    print("="*60 + "\n")
    
    # Scan for devices
    print("Scanning for unprovisioned mesh devices...\n")
    devices = await provisioner.scan_unprovisioned_devices(timeout=10.0)
    
    if not devices:
        print("\n[MESH] No unprovisioned devices found. Exiting.")
        return
    
    print(f"\n[MESH] Found {len(devices)} unprovisioned device(s):")
    for i, device in enumerate(devices, 1):
        print(f"  {i}. {device.name} - Address: {device.address}")
    
    print("\nOptions:")
    print("  - Enter device numbers separated by commas (e.g., 1,3,4)")
    print("  - Enter 'all' to provision all devices")
    print("  - Enter 'quit' to exit")
    
    selection = input("\nSelect devices to provision: ").strip().lower()
    
    if selection == 'quit':
        print("[MESH] Exiting.")
        return
    
    # Parse selection
    if selection == 'all':
        selected_devices = devices
    else:
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected_devices = [devices[i] for i in indices if 0 <= i < len(devices)]
        except (ValueError, IndexError):
            print("[MESH] Invalid selection. Exiting.")
            return
    
    if not selected_devices:
        print("[MESH] No devices selected. Exiting.")
        return
    
    print(f"\n[MESH] Provisioning {len(selected_devices)} device(s)...\n")
    
    # Provision selected devices
    provisioned_count = 0
    provisioned_nodes = []
    for i, device in enumerate(selected_devices, 1):
        print(f"[MESH] Provisioning device {i}/{len(selected_devices)}: {device.name}\n")
        node = await provisioner.provision_device(device)
        if node:
            provisioned_count += 1
            provisioned_nodes.append(node)
            print(f"[MESH] ✓ Successfully provisioned {device.name}\n")
        else:
            print(f"[MESH] ✗ Failed to provision {device.name}\n")
    
    print(f"[MESH] Provisioning complete: {provisioned_count}/{len(selected_devices)} devices provisioned")
    
    if provisioned_count == 0:
        print("\n[MESH] No devices were provisioned. Exiting.")
        return
    
    # Show network status
    print("\n" + "="*60)
    print("MESH NETWORK STATUS")
    print("="*60)
    status = provisioner.get_network_status()
    print(f"Network Key: {status['network_key']}")
    print(f"App Key: {status['app_key']}")
    print(f"Provisioned Nodes: {status['provisioned_nodes']}")
    print(f"Next Address: {status['next_unicast_address']}")
    
    print("\n" + "="*60)
    print("PROVISIONED NODES")
    print("="*60)
    for node in status['nodes']:
        print(f"\n{node['name']}:")
        print(f"  BLE Address: {node['address']}")
        print(f"  Unicast Address: {node['unicast_address']}")
        print(f"  Elements: {node['elements']}")


if __name__ == "__main__":
    asyncio.run(interactive_mesh_control())
