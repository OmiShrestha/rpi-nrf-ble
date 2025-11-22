# Author: Omi Shrestha

import asyncio
from bleak import BleakClient, BleakScanner
from ble_device import BLEDevice
from notification_handler import handle_notify

# Nordic UART Service UUIDs
CMD_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # NUS RX - Pi writes commands
EVT_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # NUS TX - Pi receives events

# Mesh network configuration
MESH_ANDROID_APP_ADDR = 0x0001  # RPi identifies as Android app to receive notifications


# Discover and Select BLE devices near the RPi
async def discover_devices(devices_dict, device_name_prefix="DART TARGETS"):
    """
    Scan for BLE devices and allow user to select one.
    
    Args:
        devices_dict: Dictionary to store discovered devices
        device_name_prefix: Prefix to filter device names
    """
    print("Scanning for BLE devices...")
    found = await BleakScanner.discover()
    discovered = []
    
    # Filter devices by name prefix
    for d in found:
        if d.name and d.name.startswith(device_name_prefix):
            target_id = d.name.split("-")[-1] if "-" in d.name else "Unknown"
            discovered.append((d.name, d.address, target_id))
    
    if not discovered:
        print("No devices found.")
        return
    
    # If multiple devices found, let the user choose one to connect
    num_devices = len(discovered)
    if num_devices > 1:
        print(f"\nFound {num_devices} devices:")
        for idx, (name, addr, tid) in enumerate(discovered, 1):
            print(f"  {idx}. {name} - MAC: {addr} (ID: {tid})")
        
        # Get user's choice
        while True:
            try:
                choice = await asyncio.to_thread(input, f"\nSelect device (1-{num_devices}): ")
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < num_devices:
                    selected = discovered[choice_idx]
                    devices_dict[selected[2]] = BLEDevice(selected[2], selected[1])
                    print(f"Selected: {selected[0]} ({selected[1]})")
                    break
                else:
                    print("Invalid selection. Try again.")
            except ValueError:
                print("Please enter a number.")
            except (EOFError, KeyboardInterrupt):
                print("\nSelection cancelled.")
                return
    else:
        # If only one device found, use it automatically
        name, addr, tid = discovered[0]
        devices_dict[tid] = BLEDevice(tid, addr)
        print(f"Found 1 device: {name} - MAC: {addr}")
    
    print("Registered devices:", list(devices_dict.keys()))


async def ensure_connected(device: BLEDevice, devices_dict):
    """
    Ensure a BLE device is connected and subscribed to notifications.
    
    Args:
        device: BLEDevice instance to connect
        devices_dict: Dictionary of all devices (passed to notification handler)
    """
    if device.client and device.client.is_connected:
        return

    device.client = BleakClient(device.address)
    await device.client.connect()
    device.connected = True
    print(f"[BLE] Connected to {device.target_id}")

    # Wait for service discovery
    await asyncio.sleep(2)
    
    # Subscribe to event notifications with device-specific callback
    def device_notify_handler(sender, data: bytearray):
        handle_notify(device, data, devices_dict)
    
    await device.client.start_notify(EVT_CHAR_UUID, device_notify_handler)
    print(f"[BLE] Subscribed to notifications for {device.target_id}")
    print(f"[BLE] Notification handler registered - ready to receive data")
    
    # Register as mesh address 0x0001 to receive firmware notifications (optional)
    # Uncomment if your firmware requires mesh registration
    # await asyncio.sleep(0.5)
    # register_cmd = f"REGISTER:{MESH_ANDROID_APP_ADDR:#06x}\n"
    # await device.client.write_gatt_char(CMD_CHAR_UUID, register_cmd.encode())
    # print(f"[MESH] Registered as address {MESH_ANDROID_APP_ADDR:#06x}")
    # await asyncio.sleep(0.5)


async def send_command(target_id, command, value, devices_dict):
    """
    Send a command to a BLE device.
    
    Args:
        target_id: ID of the target device
        command: Command string to send
        value: Optional value parameter
        devices_dict: Dictionary of all devices
    """
    if target_id not in devices_dict:
        raise Exception("Unknown target")

    device = devices_dict[target_id]
    await ensure_connected(device, devices_dict)

    if value is not None:
        packet = f"{target_id}:{command}:{value}\n"
    else:
        packet = f"{target_id}:{command}\n"

    await device.client.write_gatt_char(CMD_CHAR_UUID, packet.encode())
    print("[SEND]", packet.strip())


async def disconnect_device(device: BLEDevice):
    """
    Safely disconnect from a BLE device.
    
    Args:
        device: BLEDevice instance to disconnect
    """
    if device.client:
        try:
            if device.client.is_connected:
                await device.client.disconnect()
                print(f"Disconnected from {device.target_id}.")
        except EOFError:
            # D-Bus connection already closed, ignore
            pass
        except Exception as e:
            print(f"Disconnect error: {e}")
