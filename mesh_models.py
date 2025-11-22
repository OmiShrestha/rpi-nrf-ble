"""
Bluetooth Mesh Model Definitions
SIG-defined and vendor-specific models for mesh communication
"""

import struct
from enum import IntEnum
from typing import Optional, List
from dataclasses import dataclass

class MeshOpcode(IntEnum):
    """Standard Bluetooth Mesh opcodes"""
    # Generic OnOff Model
    GENERIC_ONOFF_GET = 0x8201
    GENERIC_ONOFF_SET = 0x8202
    GENERIC_ONOFF_SET_UNACK = 0x8203
    GENERIC_ONOFF_STATUS = 0x8204
    
    # Generic Level Model
    GENERIC_LEVEL_GET = 0x8205
    GENERIC_LEVEL_SET = 0x8206
    GENERIC_LEVEL_SET_UNACK = 0x8207
    GENERIC_LEVEL_STATUS = 0x8208
    
    # Light Lightness Model
    LIGHT_LIGHTNESS_GET = 0x824B
    LIGHT_LIGHTNESS_SET = 0x824C
    LIGHT_LIGHTNESS_SET_UNACK = 0x824D
    LIGHT_LIGHTNESS_STATUS = 0x824E
    
    # Configuration Model
    CONFIG_APPKEY_ADD = 0x00
    CONFIG_APPKEY_STATUS = 0x8003
    CONFIG_MODEL_APP_BIND = 0x803D
    CONFIG_MODEL_APP_STATUS = 0x803E

@dataclass
class GenericOnOffMessage:
    """Generic OnOff Model message"""
    onoff: bool
    tid: int = 0  # Transaction Identifier
    transition_time: Optional[int] = None
    delay: Optional[int] = None
    
    def encode_set(self, acknowledged: bool = True) -> bytes:
        """Encode as SET or SET_UNACK message"""
        opcode = MeshOpcode.GENERIC_ONOFF_SET if acknowledged else MeshOpcode.GENERIC_ONOFF_SET_UNACK
        
        # Opcode (2 bytes) + OnOff (1 byte) + TID (1 byte)
        data = struct.pack('<HBB', opcode, 1 if self.onoff else 0, self.tid)
        
        # Optional transition time and delay
        if self.transition_time is not None:
            data += struct.pack('<B', self.transition_time)
            if self.delay is not None:
                data += struct.pack('<B', self.delay)
        
        return data
    
    @staticmethod
    def encode_get() -> bytes:
        """Encode as GET message"""
        return struct.pack('<H', MeshOpcode.GENERIC_ONOFF_GET)
    
    @staticmethod
    def decode_status(data: bytes) -> 'GenericOnOffMessage':
        """Decode STATUS message"""
        if len(data) < 3:
            raise ValueError("Invalid Generic OnOff Status message")
        
        opcode, onoff = struct.unpack('<HB', data[:3])
        if opcode != MeshOpcode.GENERIC_ONOFF_STATUS:
            raise ValueError(f"Invalid opcode: 0x{opcode:04x}")
        
        msg = GenericOnOffMessage(onoff=bool(onoff))
        
        # Parse optional fields
        if len(data) >= 5:
            msg.transition_time = data[3]
            msg.delay = data[4]
        
        return msg

@dataclass
class GenericLevelMessage:
    """Generic Level Model message"""
    level: int  # -32768 to 32767
    tid: int = 0
    transition_time: Optional[int] = None
    delay: Optional[int] = None
    
    def encode_set(self, acknowledged: bool = True) -> bytes:
        """Encode as SET or SET_UNACK message"""
        opcode = MeshOpcode.GENERIC_LEVEL_SET if acknowledged else MeshOpcode.GENERIC_LEVEL_SET_UNACK
        
        # Opcode (2 bytes) + Level (2 bytes signed) + TID (1 byte)
        data = struct.pack('<Hhb', opcode, self.level, self.tid)
        
        if self.transition_time is not None:
            data += struct.pack('<B', self.transition_time)
            if self.delay is not None:
                data += struct.pack('<B', self.delay)
        
        return data
    
    @staticmethod
    def encode_get() -> bytes:
        """Encode as GET message"""
        return struct.pack('<H', MeshOpcode.GENERIC_LEVEL_GET)
    
    @staticmethod
    def decode_status(data: bytes) -> 'GenericLevelMessage':
        """Decode STATUS message"""
        if len(data) < 4:
            raise ValueError("Invalid Generic Level Status message")
        
        opcode, level = struct.unpack('<Hh', data[:4])
        if opcode != MeshOpcode.GENERIC_LEVEL_STATUS:
            raise ValueError(f"Invalid opcode: 0x{opcode:04x}")
        
        return GenericLevelMessage(level=level)

@dataclass
class SensorMessage:
    """Sensor Model message (vendor-specific example)"""
    sensor_type: int
    value: float
    
    def encode(self) -> bytes:
        """Encode sensor data"""
        # Custom vendor format: type (1 byte) + value (4 bytes float)
        return struct.pack('<Bf', self.sensor_type, self.value)
    
    @staticmethod
    def decode(data: bytes) -> 'SensorMessage':
        """Decode sensor data"""
        if len(data) < 5:
            raise ValueError("Invalid Sensor message")
        
        sensor_type, value = struct.unpack('<Bf', data[:5])
        return SensorMessage(sensor_type=sensor_type, value=value)

@dataclass
class ConfigMessage:
    """Configuration Model messages"""
    
    @staticmethod
    def encode_appkey_add(net_key_index: int, app_key_index: int, app_key: bytes) -> bytes:
        """Encode Config AppKey Add message"""
        if len(app_key) != 16:
            raise ValueError("App key must be 16 bytes")
        
        # Pack key indices (12 bits each)
        key_indices = (net_key_index & 0xFFF) | ((app_key_index & 0xFFF) << 12)
        
        return struct.pack('<BHB', 
            MeshOpcode.CONFIG_APPKEY_ADD,
            key_indices & 0xFFFF,
            (key_indices >> 16) & 0xFF
        ) + app_key
    
    @staticmethod
    def encode_model_app_bind(element_address: int, app_key_index: int, model_id: int) -> bytes:
        """Encode Config Model App Bind message"""
        return struct.pack('<BHHH',
            MeshOpcode.CONFIG_MODEL_APP_BIND,
            element_address,
            app_key_index,
            model_id
        )

# Model IDs (SIG-defined)
class ModelID(IntEnum):
    """Standard Bluetooth Mesh Model IDs"""
    CONFIGURATION_SERVER = 0x0000
    CONFIGURATION_CLIENT = 0x0001
    HEALTH_SERVER = 0x0002
    HEALTH_CLIENT = 0x0003
    
    GENERIC_ONOFF_SERVER = 0x1000
    GENERIC_ONOFF_CLIENT = 0x1001
    GENERIC_LEVEL_SERVER = 0x1002
    GENERIC_LEVEL_CLIENT = 0x1003
    
    LIGHT_LIGHTNESS_SERVER = 0x1300
    LIGHT_LIGHTNESS_CLIENT = 0x1302
    LIGHT_CTL_SERVER = 0x1303
    LIGHT_CTL_CLIENT = 0x1305
    
    SENSOR_SERVER = 0x1100
    SENSOR_CLIENT = 0x1102

def create_onoff_command(target_address: int, onoff: bool, tid: int = 0) -> dict:
    """
    Helper function to create a Generic OnOff command
    
    Args:
        target_address: Unicast address of target node
        onoff: True for ON, False for OFF
        tid: Transaction identifier (0-255)
    
    Returns:
        Dictionary with command parameters
    """
    msg = GenericOnOffMessage(onoff=onoff, tid=tid)
    return {
        "dst": target_address,
        "opcode": bytes([0x82, 0x02]),  # GENERIC_ONOFF_SET
        "params": struct.pack('BB', 1 if onoff else 0, tid)
    }

def create_level_command(target_address: int, level: int, tid: int = 0) -> dict:
    """
    Helper function to create a Generic Level command
    
    Args:
        target_address: Unicast address of target node
        level: Level value (-32768 to 32767)
        tid: Transaction identifier (0-255)
    
    Returns:
        Dictionary with command parameters
    """
    msg = GenericLevelMessage(level=level, tid=tid)
    return {
        "dst": target_address,
        "opcode": bytes([0x82, 0x06]),  # GENERIC_LEVEL_SET
        "params": struct.pack('<hB', level, tid)
    }
