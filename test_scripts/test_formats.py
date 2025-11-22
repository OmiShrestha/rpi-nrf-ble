#!/usr/bin/env python3
# Test different command formats

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
    
    client = BleakClient(board.address)
    await client.connect()
    print("Connected!")
    
    # Wait for services
    await asyncio.sleep(2)
    
    # Set up notification handler
    notifications = []
    def notify_handler(sender, data):
        try:
            msg = data.decode('utf-8').strip()
            print(f"✓ [RX] {msg}")
            notifications.append(msg)
        except:
            print(f"✓ [RX] Binary: {data.hex()}")
            notifications.append(data.hex())
    
    # Subscribe to notifications
    await client.start_notify(EVT_CHAR_UUID, notify_handler)
    print("Subscribed to notifications\n")
    
    await asyncio.sleep(1)
    
    # Test different formats
    test_cases = [
        ("firm? with \\n", b"firm?\n"),
        ("firm? with \\r\\n", b"firm?\r\n"),
        ("firm? no ending", b"firm?"),
        ("firm without ?", b"firm\n"),
        ("odo? with \\n", b"odo?\n"),
        ("odo? no ending", b"odo?"),
        ("ODO? uppercase", b"ODO?\n"),
        ("heart? with \\n", b"heart?\n"),
    ]
    
    for description, cmd_bytes in test_cases:
        print(f"Testing: {description} -> {cmd_bytes}")
        try:
            await client.write_gatt_char(CMD_CHAR_UUID, cmd_bytes)
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print(f"\n{'='*60}")
    print(f"Summary: Received {len(notifications)} notification(s)")
    print(f"{'='*60}")
    
    if notifications:
        print("Notifications received:")
        for n in notifications:
            print(f"  - {n}")
    else:
        print("\n⚠️  NO NOTIFICATIONS RECEIVED FROM ANY FORMAT!")
        print("\nThis suggests:")
        print("  1. Board firmware may not be responding to commands")
        print("  2. Board may be in a different mode or needs reset")
        print("  3. Board may need a specific initialization sequence")
        print("  4. Try resetting the board and running this test again")
    
    # Disconnect properly
    await client.disconnect()
    print("\nDisconnected")

if __name__ == "__main__":
    asyncio.run(main())
