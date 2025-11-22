# Author: Omi Shrestha

import time

def handle_notify(device, data: bytearray, devices_dict):
    """
    Handle incoming BLE notifications from firmware.
    
    Args:
        device: BLEDevice instance receiving the notification
        data: Raw notification data
        devices_dict: Dictionary of all devices (for backward compatibility)
    """
    try:
        msg = data.decode('utf-8').strip()
    except UnicodeDecodeError:
        # Handle binary data
        print(f"[NOTIFICATION] {device.target_id} - Binary data: {data.hex()}")
        device.last_notification = data
        return
    
    timestamp = time.strftime("%H:%M:%S")
    print(f"[NOTIFICATION] [{timestamp}] {device.target_id} -> {msg}")
    
    # Store in history (keep last 100 notifications)
    device.notification_history.append({
        'timestamp': timestamp,
        'message': msg,
        'raw_data': data
    })
    if len(device.notification_history) > 100:
        device.notification_history.pop(0)
    
    device.last_notification = msg
    
    # Parse different message formats
    # Format 1: "key:value" (e.g., "Voltage:12.2", "Temperature:25.5")
    if ':' in msg:
        parts = msg.split(':')
        if len(parts) == 2:
            key, value = parts
            device.data[key.strip()] = value.strip()
            print(f"  └─ Parsed: {key.strip()} = {value.strip()}")
            
            # Special handling for voltage
            if "Voltage" in key:
                try:
                    device.last_voltage = float(value)
                except ValueError:
                    pass
        
        # Format 2: "target_id:key:value" (e.g., "t01:Voltage:12.2")
        elif len(parts) == 3:
            tid, key, value = parts
            device.data[key.strip()] = value.strip()
            print(f"  └─ Parsed: {key.strip()} = {value.strip()}")
            
            if "Voltage" in key:
                try:
                    device.last_voltage = float(value)
                except ValueError:
                    pass
    
    # Format 3: JSON-like messages
    elif msg.startswith('{') and msg.endswith('}'):
        try:
            import json
            parsed = json.loads(msg)
            device.data.update(parsed)
            print(f"  └─ Parsed JSON: {parsed}")
        except json.JSONDecodeError:
            pass
    
    # Format 4: Simple status messages
    else:
        device.data['status'] = msg


def get_device_data(target_id, devices_dict):
    """
    Retrieve the latest data received from a device.
    Returns the parsed data dictionary.
    """
    if target_id not in devices_dict:
        return None
    return devices_dict[target_id].data


def get_notification_history(target_id, devices_dict, limit=10):
    """
    Get recent notification history for a device.
    """
    if target_id not in devices_dict:
        return []
    history = devices_dict[target_id].notification_history
    return history[-limit:] if len(history) > limit else history
