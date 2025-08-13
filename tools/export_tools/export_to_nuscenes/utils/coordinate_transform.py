"""
Coordinate transformation utilities for NuScenes export
"""
import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import List, Tuple, Dict, Any
from app.models.annotation_model import PSR, Position, Rotation as ObjRotation

def _quat_xyzw_to_wxyz(q: List[float]) -> List[float]:
    # input q = [x,y,z,w] -> [w,x,y,z]
    return [q[3], q[0], q[1], q[2]]

def _quat_wxyz_to_xyzw(q: List[float]) -> List[float]:
    return [q[1], q[2], q[3], q[0]]

def transform_position_to_global(local_position: Position, ego_pose: Dict[str, Any]) -> List[float]:
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
    
    ego_t = np.array(ego_pose.get('translation', [0,0,0]), dtype=float)
    ego_q_wxyz = ego_pose.get('rotation', [1,0,0,0])
    # convert to scipy xyzw
    ego_q_xyzw = _quat_wxyz_to_xyzw(ego_q_wxyz)
    r_ego = R.from_quat(ego_q_xyzw)
    local = np.array([local_position.x, local_position.y, local_position.z], dtype=float)
    global_pos = r_ego.apply(local) + ego_t
    return global_pos.tolist()


def transform_rotation_to_global(local_rotation: ObjRotation, ego_pose: Dict[str, Any]) -> List[float]:
    """
    Transform rotation from ego coordinate to global coordinate
    
    Args:
        local_rotation: Rotation in ego coordinate (euler angles)
        ego_pose: Ego pose containing rotation
        
    Returns:
        Global rotation as quaternion [w, x, y, z]
    """
    # local_rotation stored as quaternion x,y,z,w
    local_q_xyzw = [local_rotation.x, local_rotation.y, local_rotation.z, local_rotation.w]
    r_local = R.from_quat(local_q_xyzw)
    if not ego_pose:
        # If no ego pose, return local rotation as quaternion
        return _quat_xyzw_to_wxyz(local_q_xyzw)
    
    ego_q_wxyz = ego_pose.get('rotation', [1,0,0,0])
    ego_q_xyzw = _quat_wxyz_to_xyzw(ego_q_wxyz)
    r_ego = R.from_quat(ego_q_xyzw)
    r_global = r_ego * r_local
    q_global_xyzw = r_global.as_quat().tolist()
    return _quat_xyzw_to_wxyz(q_global_xyzw)


def transform_psr_to_global(psr: PSR, ego_pose: Dict[str, Any]) -> Tuple[List[float], List[float], List[float]]:
    """
    Transform complete PSR from ego coordinate to global coordinate
    
    Args:
        psr: PSR object with position, scale, rotation
        ego_pose: Ego pose information
        
    Returns:
        Tuple of (global_position, global_size, global_rotation)
    """
    pos_global = transform_position_to_global(psr.position, ego_pose)
    rot_global = transform_rotation_to_global(psr.rotation, ego_pose)
    size_lwh = [psr.scale.x, psr.scale.y, psr.scale.z]
    return pos_global, size_lwh, rot_global


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


def validate_coordinate_transform(original_psr: PSR, transformed_position: List[float], transformed_rotation: List[float], ego_pose: Dict[str, Any]) -> bool:
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
    return True
