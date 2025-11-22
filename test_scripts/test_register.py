#!/usr/bin/env python3
# Test mesh registration

import asyncio
from bleak import BleakClient, BleakScanner

CMD_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
EVT_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
MESH_ANDROID_APP_ADDR = 0x0001

async def main():
    print("Scanning...")
    devices = await BleakScanner.discover()
    
    board = None
    for d in devices:
        if d.name and d.name.startswith("DART TARGETS"):
            board = d
            break
    
    if not board:
        print("Board not found!")
        return
    
    print(f"Found: {board.name}")
    print(f"Connecting to {board.address}...")
    
    client = BleakClient(board.address)
    await client.connect()
    print("Connected!")
    
    # Wait for services
    await asyncio.sleep(2)
    
    # Set up notification handler
    def notify_handler(sender, data):
        try:
            msg = data.decode('utf-8').strip()
            print(f"✓ [NOTIFICATION] {msg}")
        except:
            print(f"✓ [NOTIFICATION] Binary: {data.hex()}")
    
    # Subscribe to notifications
    await client.start_notify(EVT_CHAR_UUID, notify_handler)
    print("Subscribed to notifications\n")
    
    await asyncio.sleep(1)
    
    # Try different REGISTER formats
    register_formats = [
        f"REGISTER:{MESH_ANDROID_APP_ADDR:#06x}\n",  # Current format: REGISTER:0x0001
        f"REGISTER {MESH_ANDROID_APP_ADDR:#06x}\n",  # With space
        f"REGISTER:{MESH_ANDROID_APP_ADDR:04x}\n",   # Lowercase hex: REGISTER:0001
        f"REGISTER {MESH_ANDROID_APP_ADDR:04x}\n",   # Space + lowercase
        f"REG:{MESH_ANDROID_APP_ADDR:#06x}\n",       # Short version
        f"register:{MESH_ANDROID_APP_ADDR:#06x}\n",  # Lowercase
    ]
    
    for reg_cmd in register_formats:
        print(f"Trying: {repr(reg_cmd)}")
        await client.write_gatt_char(CMD_CHAR_UUID, reg_cmd.encode())
        await asyncio.sleep(2)
        
        # After each register attempt, try sending a command
        print("  → Sending 'odo?' to test...")
        await client.write_gatt_char(CMD_CHAR_UUID, b"odo?\n")
        await asyncio.sleep(2)
        print()
    
    print("Test complete. Waiting 3 seconds for any delayed responses...")
    await asyncio.sleep(3)
    
    # Disconnect
    await client.disconnect()
    print("Disconnected")

if __name__ == "__main__":
    asyncio.run(main())
