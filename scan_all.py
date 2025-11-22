import asyncio
from bleak import BleakScanner

async def scan_all():
    print("Scanning for ALL BLE devices (10 seconds)...")
    devices = await BleakScanner.discover(timeout=10.0)
    
    print(f"\nFound {len(devices)} devices:\n")
    for d in devices:
        print(f"Name: {d.name or 'Unknown'}")
        print(f"Address: {d.address}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(scan_all())
