# Author: Omi Shrestha

class BLEDevice:
    """Represents a BLE device with connection and data tracking capabilities."""
    
    def __init__(self, target_id, address):
        self.target_id = target_id          # Unique identifier for the device
        self.address = address              # BLE address of the device
        self.client = None                  # GATT client instance
        self.connected = False              # Connection status
        self.last_voltage = None            # Last reported voltage
        self.last_notification = None       # Last received notification
        self.notification_history = []      # Store recent notifications
        self.data = {}                      # Store parsed data from notifications
