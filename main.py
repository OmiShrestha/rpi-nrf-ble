# Author: Omi Shrestha

import asyncio
from ble_utils import discover_devices, ensure_connected, disconnect_device, CMD_CHAR_UUID
from notification_handler import get_device_data, get_notification_history

# Global devices dictionary
devices = {}


async def main():
    """Main application entry point."""
    await discover_devices(devices)
    
    if not devices:
        print("\nNo devices found.")
        return
    
    print("\nDiscovered devices:")
    for target_id, device in devices.items():
        print(f"  - {target_id}: {device.address}")
    
    # Test connection to first device
    first_device = list(devices.values())[0]
    print(f"\nAttempting to connect to {first_device.target_id}...")
    await ensure_connected(first_device, devices)
    print("Connected!")
    print("\n" + "="*50)
    print("NOTIFICATION RECEIVER ACTIVE")
    print("All firmware notifications will be displayed below")
    print("="*50)
    
    # Interactive command loop
    print("\nCommands:")
    print("  - Type any command to send to the device")
    print("  - 'data' to view current device data")
    print("  - 'history' to view notification history")
    print("  - 'quit' to exit")
    print()
    
    while True:
        # Get user input
        try:
            command = await asyncio.to_thread(input, "Enter command: ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        
        if command.lower() == 'quit':
            break
        
        # Special commands
        elif command.lower() == 'data':
            print(f"\n[DEVICE DATA] {first_device.target_id}")
            if first_device.data:
                for key, value in first_device.data.items():
                    print(f"  {key}: {value}")
            else:
                print("  No data received yet")
            if first_device.last_voltage is not None:
                print(f"  Last Voltage: {first_device.last_voltage}V")
            print()
            continue
        
        elif command.lower() == 'history':
            print(f"\n[NOTIFICATION HISTORY] {first_device.target_id}")
            history = get_notification_history(first_device.target_id, devices, limit=20)
            if history:
                for entry in history:
                    print(f"  [{entry['timestamp']}] {entry['message']}")
            else:
                print("  No notifications received yet")
            print()
            continue
        
        # Send command to device
        await first_device.client.write_gatt_char(CMD_CHAR_UUID, command.encode())
        print(f"[SENT] {command}")
        
        # Wait for response (increased timeout for commands that return data)
        await asyncio.sleep(1.0)
    
    # Disconnect
    await disconnect_device(first_device)


if __name__ == "__main__":
    asyncio.run(main())
