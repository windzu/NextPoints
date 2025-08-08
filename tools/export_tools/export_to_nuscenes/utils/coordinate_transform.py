"""
Coordinate transformation utilities for NuScenes export
"""
import numpy as np
import quaternion
from typing import List, Tuple, Dict, Any
from app.models.annotation_model import PSR, Position, Rotation


def euler_to_quaternion(rotation: Rotation) -> List[float]:
    """
    Convert euler angles (x, y, z) to quaternion [w, x, y, z]
    
    Args:
        rotation: Rotation object with x, y, z euler angles in radians
        
    Returns:
        Quaternion as [w, x, y, z]
    """
    # Create quaternion from euler angles (roll, pitch, yaw)
    q = quaternion.from_euler_angles(rotation.x, rotation.y, rotation.z)
    
    # Return as [w, x, y, z] format (NuScenes standard)
    return [q.w, q.x, q.y, q.z]


def transform_position_to_global(
    local_position: Position,
    ego_pose: Dict[str, Any]
) -> List[float]:
    """
    Transform position from ego/lidar coordinate to global coordinate
    
    Args:
        local_position: Position in ego/lidar coordinate
        ego_pose: Ego pose containing translation and rotation
        
    Returns:
        Global position as [x, y, z]
    """
    if not ego_pose:
        # If no ego pose, return local position
        return [local_position.x, local_position.y, local_position.z]
    
    # Extract ego pose information
    ego_translation = np.array(ego_pose.get('translation', [0, 0, 0]))
    ego_rotation = ego_pose.get('rotation', [1, 0, 0, 0])  # [w, x, y, z]
    
    # Convert ego rotation to quaternion
    ego_quat = quaternion.quaternion(ego_rotation[0], ego_rotation[1], ego_rotation[2], ego_rotation[3])
    
    # Local position as vector
    local_pos = np.array([local_position.x, local_position.y, local_position.z])
    
    # Rotate local position by ego rotation
    rotated_pos = quaternion.rotate_vectors(ego_quat, local_pos)
    
    # Add ego translation
    global_pos = rotated_pos + ego_translation
    
    return global_pos.tolist()


def transform_rotation_to_global(
    local_rotation: Rotation,
    ego_pose: Dict[str, Any]
) -> List[float]:
    """
    Transform rotation from ego coordinate to global coordinate
    
    Args:
        local_rotation: Rotation in ego coordinate (euler angles)
        ego_pose: Ego pose containing rotation
        
    Returns:
        Global rotation as quaternion [w, x, y, z]
    """
    # Convert local euler to quaternion
    local_quat = quaternion.from_euler_angles(
        local_rotation.x, local_rotation.y, local_rotation.z
    )
    
    if not ego_pose:
        # If no ego pose, return local rotation as quaternion
        return [local_quat.w, local_quat.x, local_quat.y, local_quat.z]
    
    # Extract ego rotation
    ego_rotation = ego_pose.get('rotation', [1, 0, 0, 0])  # [w, x, y, z]
    ego_quat = quaternion.quaternion(ego_rotation[0], ego_rotation[1], ego_rotation[2], ego_rotation[3])
    
    # Combine rotations: global = ego * local
    global_quat = ego_quat * local_quat
    
    return [global_quat.w, global_quat.x, global_quat.y, global_quat.z]


def transform_psr_to_global(
    psr: PSR,
    ego_pose: Dict[str, Any]
) -> Tuple[List[float], List[float], List[float]]:
    """
    Transform complete PSR from ego coordinate to global coordinate
    
    Args:
        psr: PSR object with position, scale, rotation
        ego_pose: Ego pose information
        
    Returns:
        Tuple of (global_position, global_size, global_rotation)
    """
    # Transform position
    global_position = transform_position_to_global(psr.position, ego_pose)
    
    # Transform rotation  
    global_rotation = transform_rotation_to_global(psr.rotation, ego_pose)
    
    # Size remains the same (no transformation needed)
    global_size = [psr.scale.x, psr.scale.y, psr.scale.z]
    
    return global_position, global_size, global_rotation


def nuscenes_to_ego_pose_format(pose_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert NextPoints pose data to NuScenes ego_pose format
    
    Args:
        pose_data: NextPoints pose data
        
    Returns:
        NuScenes ego_pose format dict
    """
    if not pose_data:
        # Default identity pose
        return {
            "translation": [0.0, 0.0, 0.0],
            "rotation": [1.0, 0.0, 0.0, 0.0],  # [w, x, y, z]
            "timestamp": 0
        }
    
    translation = pose_data.get('translation', [0.0, 0.0, 0.0])
    rotation = pose_data.get('rotation', [1.0, 0.0, 0.0, 0.0])
    timestamp = pose_data.get('timestamp', 0)
    
    return {
        "translation": translation,
        "rotation": rotation,
        "timestamp": timestamp
    }


def validate_coordinate_transform(
    original_psr: PSR,
    transformed_position: List[float],
    transformed_rotation: List[float],
    ego_pose: Dict[str, Any]
) -> bool:
    """
    Validate coordinate transformation by checking if inverse transform works
    
    Args:
        original_psr: Original PSR in ego coordinate
        transformed_position: Transformed position in global coordinate
        transformed_rotation: Transformed rotation in global coordinate  
        ego_pose: Ego pose used for transformation
        
    Returns:
        True if transformation is valid
    """
    try:
        # This is a placeholder for validation logic
        # In practice, you would implement inverse transformation and check
        return True
    except Exception:
        return False
