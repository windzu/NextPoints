"""Pydantic schema & validation for NuScenes export (v1.0-all variant).
Strictly matches official table fields; provides cross-table validation.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field, model_validator
import math

UUID_LEN = 36  # canonical uuid string length with hyphens

class _TokenModel(BaseModel):
    token: str = Field(min_length=UUID_LEN, max_length=UUID_LEN)

class SceneModel(_TokenModel):
    name: str
    description: str
    log_token: str
    nbr_samples: int
    first_sample_token: str
    last_sample_token: str

class SampleModel(_TokenModel):
    timestamp: int
    prev: str
    next: str
    scene_token: str

class SampleDataModel(_TokenModel):
    sample_token: str
    ego_pose_token: str
    calibrated_sensor_token: str
    timestamp: int
    fileformat: str
    is_key_frame: bool
    filename: str
    prev: str = ""
    next: str = ""
    height: Optional[int] = None
    width: Optional[int] = None

class EgoPoseModel(_TokenModel):
    timestamp: int
    rotation: List[float]  # w,x,y,z
    translation: List[float]  # x,y,z

    @model_validator(mode="after")
    def _validate_lists(self):  # type: ignore
        if len(self.rotation) != 4:
            raise ValueError("ego_pose.rotation must have 4 floats")
        if len(self.translation) != 3:
            raise ValueError("ego_pose.translation must have 3 floats")
        # normalize check
        norm = math.sqrt(sum(c*c for c in self.rotation))
        if not (0.999 <= norm <= 1.001):
            raise ValueError("ego_pose.rotation quaternion not normalized")
        return self

class SensorModel(_TokenModel):
    channel: str
    modality: str

class CalibratedSensorModel(_TokenModel):
    sensor_token: str
    translation: List[float]
    rotation: List[float]
    camera_intrinsic: Optional[List[List[float]]] = None

    @model_validator(mode="after")
    def _check(self):  # type: ignore
        if len(self.translation) != 3:
            raise ValueError("calibrated_sensor.translation must be 3 elements")
        if len(self.rotation) != 4:
            raise ValueError("calibrated_sensor.rotation must be 4 elements")
        norm = math.sqrt(sum(c*c for c in self.rotation))
        if not (0.999 <= norm <= 1.001):
            raise ValueError("calibrated_sensor.rotation quaternion not normalized")
        if self.camera_intrinsic is not None:
            if len(self.camera_intrinsic) != 3 or any(len(r) != 3 for r in self.camera_intrinsic):
                raise ValueError("camera_intrinsic must be 3x3 matrix")
        return self

class LogModel(_TokenModel):
    logfile: str
    vehicle: str
    date_captured: str
    location: str

class CategoryModel(_TokenModel):
    name: str
    description: str

class AttributeModel(_TokenModel):
    name: str
    description: str

class VisibilityModel(_TokenModel):
    level: str
    description: str

class MapModel(_TokenModel):
    log_tokens: List[str]
    category: str
    filename: str

class InstanceModel(_TokenModel):
    category_token: str
    nbr_annotations: int
    first_annotation_token: str
    last_annotation_token: str

class SampleAnnotationModel(_TokenModel):
    sample_token: str
    instance_token: str
    visibility_token: str
    attribute_tokens: List[str]
    translation: List[float]
    size: List[float]  # w,l,h
    rotation: List[float]  # w,x,y,z
    prev: str
    next: str
    num_lidar_pts: int
    num_radar_pts: int

    @model_validator(mode="after")
    def _check(self):  # type: ignore
        if len(self.translation) != 3:
            raise ValueError("sample_annotation.translation must be 3")
        if len(self.size) != 3:
            raise ValueError("sample_annotation.size must be 3 (w,l,h)")
        if any(s <= 0 for s in self.size):
            raise ValueError("sample_annotation.size values must be >0")
        if len(self.rotation) != 4:
            raise ValueError("sample_annotation.rotation must have 4 floats")
        norm = math.sqrt(sum(c*c for c in self.rotation))
        if not (0.999 <= norm <= 1.001):
            raise ValueError("sample_annotation.rotation quaternion not normalized")
        return self

class NuScenesTables(BaseModel):
    scene: List[SceneModel]
    sample: List[SampleModel]
    sample_data: List[SampleDataModel]
    ego_pose: List[EgoPoseModel]
    sensor: List[SensorModel]
    calibrated_sensor: List[CalibratedSensorModel]
    log: List[LogModel]
    category: List[CategoryModel]
    attribute: List[AttributeModel]
    visibility: List[VisibilityModel]
    map: List[MapModel]
    instance: List[InstanceModel]
    sample_annotation: List[SampleAnnotationModel]


def cross_validate(tables: NuScenesTables) -> List[str]:
    errors: List[str] = []
    # Token uniqueness
    seen: Set[str] = set()
    for name, records in tables.model_dump().items():  # type: ignore
        for rec in records:
            tok = rec['token']
            if tok in seen:
                errors.append(f"Duplicate token across tables: {tok} (table {name})")
            seen.add(tok)
    # Build token sets
    sample_tokens = {s.token for s in tables.sample}
    scene_samples: Dict[str, List[str]] = {}
    for s in tables.sample:
        scene_samples.setdefault(s.scene_token, []).append(s.token)
    # Scene checks
    for sc in tables.scene:
        if sc.first_sample_token not in sample_tokens:
            errors.append(f"Scene {sc.token} first_sample_token missing")
        if sc.last_sample_token not in sample_tokens:
            errors.append(f"Scene {sc.token} last_sample_token missing")
        sample_list = scene_samples.get(sc.token, [])
        if sc.nbr_samples != len(sample_list):
            errors.append(f"Scene {sc.token} nbr_samples mismatch {sc.nbr_samples}!={len(sample_list)}")
    # Sample chain integrity (prev/next symmetry)
    for s in tables.sample:
        if s.prev:
            if s.prev not in sample_tokens:
                errors.append(f"Sample {s.token} prev missing {s.prev}")
        if s.next:
            if s.next not in sample_tokens:
                errors.append(f"Sample {s.token} next missing {s.next}")
    # Collect other tokens
    ego_pose_tokens = {e.token for e in tables.ego_pose}
    calib_tokens = {c.token for c in tables.calibrated_sensor}
    sensor_tokens = {s.token for s in tables.sensor}
    instance_tokens = {i.token for i in tables.instance}
    category_tokens = {c.token for c in tables.category}
    attribute_tokens = {a.token for a in tables.attribute}
    visibility_tokens = {v.token for v in tables.visibility}
    annotation_tokens = {a.token for a in tables.sample_annotation}
    # sample_data fk
    for sd in tables.sample_data:
        if sd.sample_token not in sample_tokens:
            errors.append(f"sample_data {sd.token} references missing sample {sd.sample_token}")
        if sd.ego_pose_token not in ego_pose_tokens:
            errors.append(f"sample_data {sd.token} missing ego_pose {sd.ego_pose_token}")
        if sd.calibrated_sensor_token not in calib_tokens:
            errors.append(f"sample_data {sd.token} missing calibrated_sensor {sd.calibrated_sensor_token}")
    # calibrated_sensor -> sensor
    for c in tables.calibrated_sensor:
        if c.sensor_token not in sensor_tokens:
            errors.append(f"calibrated_sensor {c.token} missing sensor {c.sensor_token}")
    # instance checks / annotation linkage
    ann_by_instance: Dict[str, List[str]] = {}
    ann_first_last: Dict[str, List[str]] = {}
    for ann in tables.sample_annotation:
        if ann.instance_token not in instance_tokens:
            errors.append(f"sample_annotation {ann.token} missing instance {ann.instance_token}")
        if ann.visibility_token not in visibility_tokens:
            errors.append(f"sample_annotation {ann.token} missing visibility {ann.visibility_token}")
        for atok in ann.attribute_tokens:
            if atok not in attribute_tokens:
                errors.append(f"sample_annotation {ann.token} missing attribute {atok}")
        ann_by_instance.setdefault(ann.instance_token, []).append(ann.token)
    for inst in tables.instance:
        if inst.category_token not in category_tokens:
            errors.append(f"instance {inst.token} missing category {inst.category_token}")
        lst = ann_by_instance.get(inst.token, [])
        if inst.nbr_annotations != len(lst):
            errors.append(f"instance {inst.token} nbr_annotations mismatch {inst.nbr_annotations}!={len(lst)}")
        if lst:
            if inst.first_annotation_token not in annotation_tokens:
                errors.append(f"instance {inst.token} first_annotation missing {inst.first_annotation_token}")
            if inst.last_annotation_token not in annotation_tokens:
                errors.append(f"instance {inst.token} last_annotation missing {inst.last_annotation_token}")
    return errors
