"""
Token generator for NuScenes format
"""
import uuid
import hashlib
from typing import Union


def generate_uuid_from_input(input_str: str) -> str:
    """
    Generate deterministic UUID from input string
    Based on roscenes implementation
    """
    # Create SHA256 hash of input
    hash_bytes = hashlib.sha256(input_str.encode('utf-8')).digest()
    
    # Use first 16 bytes to create UUID
    return str(uuid.UUID(bytes=hash_bytes[:16]))


def generate_scene_token(scene_name: str) -> str:
    """Generate scene token"""
    return generate_uuid_from_input(f"scene-{scene_name}")


def generate_log_token(scene_name: str) -> str:
    """Generate log token"""
    return generate_uuid_from_input(f"log-{scene_name}")


def generate_sample_token(scene_name: str, timestamp: Union[str, int]) -> str:
    """Generate sample token"""
    return generate_uuid_from_input(f"sample-{scene_name}-{timestamp}")


def generate_sample_data_token(scene_name: str, timestamp: Union[str, int], channel: str) -> str:
    """Generate sample_data token"""
    return generate_uuid_from_input(f"sample_data-{scene_name}-{timestamp}-{channel}")


def generate_annotation_token(scene_name: str, timestamp: Union[str, int], obj_id: str) -> str:
    """Generate sample_annotation token"""
    return generate_uuid_from_input(f"annotation-{scene_name}-{timestamp}-{obj_id}")


def generate_instance_token(scene_name: str, track_id: str) -> str:
    """Generate instance token"""
    return generate_uuid_from_input(f"instance-{scene_name}-{track_id}")


def generate_ego_pose_token(scene_name: str, timestamp: Union[str, int]) -> str:
    """Generate ego_pose token"""
    return generate_uuid_from_input(f"ego_pose-{scene_name}-{timestamp}")


def generate_calibrated_sensor_token(scene_name: str, sensor_name: str) -> str:
    """Generate calibrated_sensor token"""
    return generate_uuid_from_input(f"calibrated_sensor-{scene_name}-{sensor_name}")


def generate_sensor_token(sensor_name: str) -> str:
    """Generate sensor token"""
    return generate_uuid_from_input(f"sensor-{sensor_name}")
