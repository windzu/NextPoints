"""
NuScenes annotation and instance schema models (migrated to direct Pydantic models)
"""
from typing import List, Dict
from .pydantic_models import InstanceModel, SampleAnnotationModel


class InstanceTracker:
    """Track instances across frames for trajectory building using Pydantic models"""
    
    def __init__(self):
        self.instances: Dict[str, Dict] = {}  # instance_token -> info dict
        self.annotations_by_instance: Dict[str, List[SampleAnnotationModel]] = {}
        self.annotation_timestamps: Dict[str, int] = {}
    
    def add_annotation(
        self,
        scene_name: str,
        track_id: str,
        category_token: str,
        annotation: SampleAnnotationModel,
        timestamp_us: int
    ) -> str:
        from ..utils import generate_instance_token
        instance_token = generate_instance_token(scene_name, track_id)
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
        inst_info = self.instances[instance_token]
        inst_info["nbr_annotations"] += 1
        inst_info["last_annotation_token"] = annotation.token
        self.annotations_by_instance[instance_token].append(annotation)
        self.annotation_timestamps[annotation.token] = timestamp_us
        return instance_token
    
    def finalize_instances(self) -> List[InstanceModel]:
        for instance_token, annotations in self.annotations_by_instance.items():
            annotations.sort(key=lambda a: self.annotation_timestamps.get(a.token, 0))
            for i, ann in enumerate(annotations):
                ann.prev = annotations[i-1].token if i > 0 else ""
                ann.next = annotations[i+1].token if i < len(annotations)-1 else ""
            if annotations:
                inst_info = self.instances[instance_token]
                inst_info["first_annotation_token"] = annotations[0].token
                inst_info["last_annotation_token"] = annotations[-1].token
        instances: List[InstanceModel] = []
        for info in self.instances.values():
            instances.append(InstanceModel(
                token=info["token"],
                category_token=info["category_token"],
                nbr_annotations=info["nbr_annotations"],
                first_annotation_token=info["first_annotation_token"],
                last_annotation_token=info["last_annotation_token"]
            ))
        return instances
    
    def get_all_annotations(self) -> List[SampleAnnotationModel]:
        all_anns: List[SampleAnnotationModel] = []
        for lst in self.annotations_by_instance.values():
            all_anns.extend(lst)
        return all_anns
