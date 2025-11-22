#!/usr/bin/env python3
# Simple test without REGISTER command

import asyncio
from bleak import BleakClient, BleakScanner

CMD_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
EVT_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

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
    
    async with BleakClient(board.address) as client:
        print("Connected!")
        
        # Wait for services
        await asyncio.sleep(2)
        
        # Set up notification handler
        def notify_handler(sender, data):
            try:
                msg = data.decode('utf-8').strip()
                print(f"[RX] {msg}")
            except:
                print(f"[RX] Binary: {data.hex()}")
        
        # Subscribe to notifications
        await client.start_notify(EVT_CHAR_UUID, notify_handler)
        print("Subscribed to notifications")
        
        # Wait a bit
        await asyncio.sleep(1)
        
        # Try commands WITHOUT the REGISTER step
        commands = ["firm?", "odo?", "heart?", "blink?"]
        
        for cmd in commands:
            print(f"\n[TX] {cmd}")
            await client.write_gatt_char(CMD_CHAR_UUID, (cmd + "\n").encode())
            await asyncio.sleep(2)  # Wait for response
        
        print("\nTest complete. Waiting 3 more seconds...")
        await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
