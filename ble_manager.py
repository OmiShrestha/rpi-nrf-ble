# Author: Omi Shrestha
# Legacy entry point - imports and re-exports modular components

"""
BLE Manager - Legacy compatibility layer
This file maintains backward compatibility while using the new modular structure.
For new code, use main.py or import from individual modules.
"""

import asyncio
from ble_device import BLEDevice
from ble_utils import (
    discover_devices as _discover_devices,
    ensure_connected as _ensure_connected,
    send_command as _send_command,
    disconnect_device,
    CMD_CHAR_UUID,
    EVT_CHAR_UUID,
    MESH_ANDROID_APP_ADDR
)
from notification_handler import (
    handle_notify,
    get_device_data,
    get_notification_history
)

# Global devices dictionary for backward compatibility
devices = {}


# Wrapper functions to maintain backward compatibility
async def discover_devices():
    """Discover BLE devices (legacy wrapper)."""
    await _discover_devices(devices)


async def ensure_connected(device):
    """Ensure device is connected (legacy wrapper)."""
    await _ensure_connected(device, devices)


async def send_command(target_id, command, value=None):
    """Send command to device (legacy wrapper)."""
    await _send_command(target_id, command, value, devices)


# Main function to test scanning
async def main():
    """Main entry point (legacy)."""
    await discover_devices()
    
    if not devices:
        print("\nNo devices found.")
        return
    
    print("\nDiscovered devices:")
    for target_id, device in devices.items():
        print(f"  - {target_id}: {device.address}")
    
    # Test connection to first device
    first_device = list(devices.values())[0]
    print(f"\nAttempting to connect to {first_device.target_id}...")
    await ensure_connected(first_device)
    print("Connected!")
    
    # Interactive command loop
    print("\nType commands to send to the device (or 'quit' to exit):")
    
    while True:
        # Get user input
        try:
            command = await asyncio.to_thread(input, "Enter command: ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        
        if command.lower() == 'quit':
            break
        
        # Send command
        await first_device.client.write_gatt_char(CMD_CHAR_UUID, (command + "\n").encode())
        print(f"[SENT] {command}")
        
        # Wait a bit for response
        await asyncio.sleep(0.5)
    
    # Disconnect
    await disconnect_device(first_device)


if __name__ == "__main__":
    asyncio.run(main())
