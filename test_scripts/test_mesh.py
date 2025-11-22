#!/usr/bin/env python3
# Test with Mesh Proxy characteristic

import asyncio
from bleak import BleakClient, BleakScanner

# Nordic UART Service
CMD_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # UART RX (write)
EVT_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # UART TX (notify)

# Mesh Proxy Service
MESH_DATA_IN_UUID = "00002add-0000-1000-8000-00805f9b34fb"   # Mesh Proxy Data In (write)
MESH_DATA_OUT_UUID = "00002ade-0000-1000-8000-00805f9b34fb"  # Mesh Proxy Data Out (notify)

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
    
    # Set up notification handlers
    def uart_notify_handler(sender, data):
        try:
            msg = data.decode('utf-8').strip()
            print(f"[UART RX] {msg}")
        except:
            print(f"[UART RX] Binary: {data.hex()}")
    
    def mesh_notify_handler(sender, data):
        try:
            msg = data.decode('utf-8').strip()
            print(f"✓✓✓ [MESH RX] {msg}")
        except:
            print(f"✓✓✓ [MESH RX] Binary: {data.hex()}")
    
    # Subscribe to BOTH characteristics
    print("\nSubscribing to UART TX notifications...")
    await client.start_notify(EVT_CHAR_UUID, uart_notify_handler)
    print("✓ Subscribed to UART TX")
    
    print("\nSubscribing to MESH PROXY DATA OUT notifications...")
    await client.start_notify(MESH_DATA_OUT_UUID, mesh_notify_handler)
    print("✓ Subscribed to MESH PROXY DATA OUT")
    
    await asyncio.sleep(1)
    
    # Test commands
    print("\n" + "="*60)
    print("Sending commands via UART RX...")
    print("="*60)
    
    commands = ["firm?", "odo?", "heart?"]
    
    for cmd in commands:
        print(f"\n[UART TX] {cmd}")
        await client.write_gatt_char(CMD_CHAR_UUID, (cmd + "\n").encode())
        await asyncio.sleep(2)
    
    print("\n" + "="*60)
    print("Waiting 5 more seconds for any responses...")
    print("="*60)
    await asyncio.sleep(5)
    
    # Disconnect
    await client.disconnect()
    print("\nDisconnected")

if __name__ == "__main__":
    asyncio.run(main())
