"""
Bluetooth Mesh Provisioner Main Script
Interactive CLI for provisioning and controlling mesh devices
"""

import asyncio
from mesh_provisioner import interactive_mesh_control

if __name__ == "__main__":
    try:
        asyncio.run(interactive_mesh_control())
    except KeyboardInterrupt:
        print("\n\n[MESH] Interrupted by user")
    except Exception as e:
        print(f"\n[MESH] Error: {e}")
