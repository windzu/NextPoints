"""
NuScenes annotation and instance schema models
"""
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass 
class NuScenesInstance:
    """NuScenes instance data model"""
    token: str
    category_token: str
    nbr_annotations: int
    first_annotation_token: str
    last_annotation_token: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "category_token": self.category_token,
            "nbr_annotations": self.nbr_annotations,
            "first_annotation_token": self.first_annotation_token,
            "last_annotation_token": self.last_annotation_token
        }


@dataclass
class NuScenesSampleAnnotation:
    """NuScenes sample_annotation data model"""
    token: str
    sample_token: str
    instance_token: str
    visibility_token: str
    attribute_tokens: List[str]
    translation: List[float]  # [x, y, z] in global coordinates
    size: List[float]  # [width, length, height] 
    rotation: List[float]  # [w, x, y, z] quaternion in global coordinates
    prev: str
    next: str
    num_lidar_pts: int
    num_radar_pts: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "sample_token": self.sample_token,
            "instance_token": self.instance_token,
            "visibility_token": self.visibility_token,
            "attribute_tokens": self.attribute_tokens,
            "translation": self.translation,
            "size": self.size,
            "rotation": self.rotation,
            "prev": self.prev,
            "next": self.next,
            "num_lidar_pts": self.num_lidar_pts,
            "num_radar_pts": self.num_radar_pts
        }


class InstanceTracker:
    """Track instances across frames for trajectory building"""
    
    def __init__(self):
        self.instances: Dict[str, Dict] = {}  # track_id -> instance_info
        self.annotations_by_instance: Dict[str, List] = {}  # instance_token -> annotation_list
        
    def add_annotation(
        self,
        scene_name: str,
        track_id: str,
        category_token: str,
        annotation: NuScenesSampleAnnotation
    ) -> str:
        """
        Add annotation to instance tracker
        
        Args:
            scene_name: Scene name
            track_id: Object track ID from NextPoints
            category_token: NuScenes category token
            annotation: Sample annotation
            
        Returns:
            Instance token
        """
        from ..utils import generate_instance_token
        
        instance_token = generate_instance_token(scene_name, track_id)
        
        # Initialize instance if not exists
        if instance_token not in self.instances:
            self.instances[instance_token] = {
                "token": instance_token,
                "category_token": category_token,
                "track_id": track_id,
                "scene_name": scene_name,
                "nbr_annotations": 0,
                "first_annotation_token": annotation.token,
                "last_annotation_token": annotation.token
            }
            self.annotations_by_instance[instance_token] = []
        
        # Update instance info
        instance_info = self.instances[instance_token]
        instance_info["nbr_annotations"] += 1
        instance_info["last_annotation_token"] = annotation.token
        
        # Add annotation to list
        self.annotations_by_instance[instance_token].append(annotation)
        
        return instance_token
    
    def finalize_instances(self) -> List[NuScenesInstance]:
        """
        Finalize all instances and link annotations
        
        Returns:
            List of NuScenesInstance objects
        """
        # Link annotations within each instance (prev/next)
        for instance_token, annotations in self.annotations_by_instance.items():
            # Sort annotations by timestamp
            annotations.sort(key=lambda x: x.sample_token)
            
            # Link prev/next
            for i, annotation in enumerate(annotations):
                if i > 0:
                    annotation.prev = annotations[i-1].token
                else:
                    annotation.prev = ""
                    
                if i < len(annotations) - 1:
                    annotation.next = annotations[i+1].token
                else:
                    annotation.next = ""
        
        # Create instance objects
        instances = []
        for instance_info in self.instances.values():
            instance = NuScenesInstance(
                token=instance_info["token"],
                category_token=instance_info["category_token"],
                nbr_annotations=instance_info["nbr_annotations"],
                first_annotation_token=instance_info["first_annotation_token"],
                last_annotation_token=instance_info["last_annotation_token"]
            )
            instances.append(instance)
        
        return instances
    
    def get_all_annotations(self) -> List[NuScenesSampleAnnotation]:
        """Get all annotations from all instances"""
        all_annotations = []
        for annotations in self.annotations_by_instance.values():
            all_annotations.extend(annotations)
        return all_annotations
