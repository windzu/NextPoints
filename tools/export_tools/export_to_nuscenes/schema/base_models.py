"""
NuScenes data schema models
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class NuScenesScene:
    """NuScenes scene data model"""
    token: str
    name: str
    description: str
    log_token: str
    nbr_samples: int
    first_sample_token: str
    last_sample_token: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "name": self.name,
            "description": self.description,
            "log_token": self.log_token,
            "nbr_samples": self.nbr_samples,
            "first_sample_token": self.first_sample_token,
            "last_sample_token": self.last_sample_token
        }


@dataclass
class NuScenesSample:
    """NuScenes sample data model (official fields only)."""
    token: str
    timestamp: int
    prev: str
    next: str
    scene_token: str
    data: Optional[Dict[str, str]] = None  # kept internally, excluded in output
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "timestamp": self.timestamp,
            "prev": self.prev,
            "next": self.next,
            "scene_token": self.scene_token
        }


@dataclass
class NuScenesSampleData:
    """NuScenes sample_data data model"""
    token: str
    sample_token: str
    ego_pose_token: str
    calibrated_sensor_token: str
    timestamp: int
    fileformat: str
    is_key_frame: bool
    height: Optional[int] = None
    width: Optional[int] = None
    filename: str = ""
    prev: str = ""
    next: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "token": self.token,
            "sample_token": self.sample_token,
            "ego_pose_token": self.ego_pose_token,
            "calibrated_sensor_token": self.calibrated_sensor_token,
            "timestamp": self.timestamp,
            "fileformat": self.fileformat,
            "is_key_frame": self.is_key_frame,
            "filename": self.filename,
            "prev": self.prev,
            "next": self.next
        }
        
        # Add optional fields if they exist
        if self.height is not None:
            result["height"] = self.height
        if self.width is not None:
            result["width"] = self.width
            
        return result


@dataclass
class NuScenesEgoPose:
    """NuScenes ego_pose data model"""
    token: str
    timestamp: int
    rotation: List[float]  # [w, x, y, z] quaternion
    translation: List[float]  # [x, y, z]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "timestamp": self.timestamp,
            "rotation": self.rotation,
            "translation": self.translation
        }


@dataclass
class NuScenesSensor:
    """NuScenes sensor data model"""
    token: str
    channel: str
    modality: str  # 'lidar', 'camera', 'radar'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "channel": self.channel,
            "modality": self.modality
        }


@dataclass
class NuScenesCalibratedSensor:
    """NuScenes calibrated_sensor data model"""
    token: str
    sensor_token: str
    translation: List[float]  # [x, y, z]
    rotation: List[float]  # [w, x, y, z] quaternion
    camera_intrinsic: Optional[List[List[float]]] = None  # 3x3 matrix for cameras
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "token": self.token,
            "sensor_token": self.sensor_token,
            "translation": self.translation,
            "rotation": self.rotation
        }
        
        if self.camera_intrinsic is not None:
            result["camera_intrinsic"] = self.camera_intrinsic
            
        return result


@dataclass
class NuScenesLog:
    """NuScenes log data model"""
    token: str
    logfile: str
    vehicle: str
    date_captured: str
    location: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "logfile": self.logfile,
            "vehicle": self.vehicle,
            "date_captured": self.date_captured,
            "location": self.location
        }


@dataclass
class NuScenesCategory:
    """NuScenes category data model"""
    token: str
    name: str
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "name": self.name,
            "description": self.description
        }


@dataclass
class NuScenesAttribute:
    """NuScenes attribute data model"""
    token: str
    name: str
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "name": self.name,
            "description": self.description
        }


@dataclass
class NuScenesVisibility:
    """NuScenes visibility data model"""
    token: str
    level: str
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "level": self.level,
            "description": self.description
        }


@dataclass
class NuScenesMap:
    """NuScenes map data model"""
    token: str
    log_tokens: List[str]
    category: str
    filename: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "log_tokens": self.log_tokens,
            "category": self.category,
            "filename": self.filename
        }
