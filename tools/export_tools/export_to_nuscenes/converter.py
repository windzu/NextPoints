"""
Main converter for NextPoints to NuScenes format (refactored: use v1.0-all split)
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import binascii

from app.models.meta_data_model import ProjectMetadataResponse, FrameMetadata
from app.models.export_model import NuScenesExportRequest
from app.models.annotation_model import AnnotationItem

from .schema import (
    NuScenesScene, NuScenesSample, NuScenesSampleData, NuScenesEgoPose,
    NuScenesSensor, NuScenesCalibratedSensor, NuScenesLog, NuScenesCategory,
    NuScenesAttribute, NuScenesVisibility, NuScenesMap, NuScenesInstance,
    NuScenesSampleAnnotation, InstanceTracker
)
from .schema.pydantic_models import (
    SceneModel, SampleModel, SampleDataModel, EgoPoseModel, SensorModel,
    CalibratedSensorModel, LogModel, CategoryModel, AttributeModel,
    VisibilityModel, MapModel, InstanceModel, SampleAnnotationModel,
    NuScenesTables, cross_validate
)

from .utils import (
    generate_scene_token, generate_log_token, generate_sample_token,
    generate_sample_data_token, generate_annotation_token, generate_ego_pose_token,
    generate_calibrated_sensor_token, generate_sensor_token,
    transform_psr_to_global, nuscenes_to_ego_pose_format,
    create_nuscenes_directory_structure, save_json_table, copy_sensor_data,
    generate_nuscenes_filename, validate_nuscenes_structure
)

from .category_mapping import (
    get_nuscenes_category, get_default_attributes, validate_category_size,
    get_all_nuscenes_categories, get_all_nuscenes_attributes,
    NUSCENES_VISIBILITY
)


class NextPointsToNuScenesConverter:
    """Main converter class for NextPoints to NuScenes format"""
    
    def __init__(self, project_metadata: ProjectMetadataResponse, export_request: NuScenesExportRequest):
        self.project_metadata = project_metadata
        self.export_request = export_request
        self.scene_name = project_metadata.project.name
        
        # Data containers
        self.scenes: List[NuScenesScene] = []
        self.samples: List[NuScenesSample] = []
        self.sample_data: List[NuScenesSampleData] = []
        self.ego_poses: List[NuScenesEgoPose] = []
        self.sensors: List[NuScenesSensor] = []
        self.calibrated_sensors: List[NuScenesCalibratedSensor] = []
        self.logs: List[NuScenesLog] = []
        self.categories: List[NuScenesCategory] = []
        self.attributes: List[NuScenesAttribute] = []
        self.visibility: List[NuScenesVisibility] = []
        self.maps: List[NuScenesMap] = []
        
        # Annotation tracking
        self.instance_tracker = InstanceTracker()
        
        # Tokens cache
        self.category_tokens: Dict[str, str] = {}
        self.attribute_tokens: Dict[str, str] = {}
        self.sensor_tokens: Dict[str, str] = {}
        self.calibrated_sensor_tokens: Dict[str, str] = {}
        
        # Statistics
        self.stats = {
            "frames_processed": 0,
            "annotations_converted": 0,
            "instances_created": 0,
            "errors": []
        }
    
    def convert(self, output_dir: Path) -> Dict[str, Any]:
        """Main conversion method (will be further tightened with Pydantic)."""
        try:
            # Collect dynamic sensor channels (lidar main + cameras)
            sensor_channels = [self.project_metadata.main_channel]
            for ch, calib in self.project_metadata.calibration.items():
                if getattr(calib, 'camera_config', None):
                    if ch not in sensor_channels:
                        sensor_channels.append(ch)
            directories = create_nuscenes_directory_structure(output_dir, sensor_channels=sensor_channels)
            # Write black map file
            map_file_path = directories['maps'] / self._black_map_filename
            if not map_file_path.exists():
                with open(map_file_path, 'wb') as f:
                    f.write(self._black_map_content)
            self._initialize_static_data()
            self._process_frames(directories)
            self._finalize_annotations()
            # NOTE: changed split dir to v1.0-all
            self._save_json_tables(directories['v1.0-all'])
            validation_errors = validate_nuscenes_structure(output_dir)
            if validation_errors:
                self.stats["errors"].extend(validation_errors)
            return self.stats
        except Exception as e:
            self.stats["errors"].append(f"Conversion failed: {str(e)}")
            raise e
    
    def _initialize_static_data(self):
        """Initialize static NuScenes data (categories, attributes, etc.)"""
        # Categories
        for category_name in get_all_nuscenes_categories():
            token = generate_sensor_token(f"category_{category_name}")
            self.category_tokens[category_name] = token
            
            category = NuScenesCategory(
                token=token,
                name=category_name,
                description=f"NuScenes category: {category_name}"
            )
            self.categories.append(category)
        
        # Attributes
        for attr_name in get_all_nuscenes_attributes():
            token = generate_sensor_token(f"attribute_{attr_name}")
            self.attribute_tokens[attr_name] = token
            
            attribute = NuScenesAttribute(
                token=token,
                name=attr_name,
                description=f"NuScenes attribute: {attr_name}"
            )
            self.attributes.append(attribute)
        
        # Visibility levels
        for level, token in NUSCENES_VISIBILITY.items():
            visibility = NuScenesVisibility(
                token=token,
                level=level,
                description=f"Visibility: {level}"
            )
            self.visibility.append(visibility)
        
        # Sensors and calibrated sensors from project metadata
        self._initialize_sensors()
        
        # Log
        log_token = generate_log_token(self.scene_name)
        log = NuScenesLog(
            token=log_token,
            logfile=f"{self.scene_name}.log",
            vehicle="vehicle",
            date_captured=datetime.utcnow().strftime("%Y-%m-%d"),
            location="unknown"
        )
        self.logs.append(log)
        
        # Scene
        scene_token = generate_scene_token(self.scene_name)
        first_sample_token = generate_sample_token(self.scene_name, self.project_metadata.frames[0].timestamp_ns)
        last_sample_token = generate_sample_token(self.scene_name, self.project_metadata.frames[-1].timestamp_ns)
        
        scene = NuScenesScene(
            token=scene_token,
            name=self.scene_name,
            description=f"Exported from NextPoints project: {self.scene_name}",
            log_token=log_token,
            nbr_samples=len(self.project_metadata.frames),
            first_sample_token=first_sample_token,
            last_sample_token=last_sample_token
        )
        self.scenes.append(scene)
        
        # Default map (required by NuScenes SDK) create 1x1 black png
        map_token = generate_sensor_token(f"map_{self.scene_name}")
        black_png_bytes = binascii.unhexlify(
            b"89504E470D0A1A0A0000000D49484452000000010000000108020000009077053D0000000A49444154789C636000000200018D0D0A2DB40000000049454E44AE426082"
        )
        self._black_map_content = black_png_bytes
        self._black_map_filename = "default_map.png"
        default_map = NuScenesMap(
            token=map_token,
            log_tokens=[log_token],
            category="semantic_prior",
            filename=f"maps/{self._black_map_filename}"
        )
        self.maps.append(default_map)
    
    def _initialize_sensors(self):
        """Initialize sensors from calibration data"""
        calibration = self.project_metadata.calibration
        main_channel = self.project_metadata.main_channel

        # LIDAR sensor uses its original channel name
        lidar_sensor_token = generate_sensor_token(main_channel)
        self.sensor_tokens[main_channel] = lidar_sensor_token

        lidar_sensor = NuScenesSensor(
            token=lidar_sensor_token,
            channel=main_channel,
            modality="lidar"
        )
        self.sensors.append(lidar_sensor)

        # LIDAR calibrated sensor (identity assuming overlap with base_link)
        lidar_calib_token = generate_calibrated_sensor_token(self.scene_name, main_channel)
        self.calibrated_sensor_tokens[main_channel] = lidar_calib_token

        lidar_calib = NuScenesCalibratedSensor(
            token=lidar_calib_token,
            sensor_token=lidar_sensor_token,
            translation=[0.0, 0.0, 0.0],
            rotation=[1.0, 0.0, 0.0, 0.0]
        )
        self.calibrated_sensors.append(lidar_calib)

        # Camera sensors
        for channel, calib_data in calibration.items():
            if calib_data.camera_config:
                self._add_camera_sensor(channel, calib_data)

    def _add_camera_sensor(self, camera_name: str, calib_data: Any):
        """Add camera sensor and calibrated sensor using raw channel name"""
        camera_channel = camera_name  # keep original
        sensor_token = generate_sensor_token(camera_channel)
        self.sensor_tokens[camera_channel] = sensor_token

        sensor = NuScenesSensor(
            token=sensor_token,
            channel=camera_channel,
            modality="camera"
        )
        self.sensors.append(sensor)

        calib_token = generate_calibrated_sensor_token(self.scene_name, camera_channel)
        self.calibrated_sensor_tokens[camera_channel] = calib_token

        try:
            # Extract extrinsic from pose (base_link->sensor) if available
            pose = calib_data.pose.transform if calib_data and calib_data.pose else None
            if pose:
                t = pose.translation
                translation = [t.x, t.y, t.z]
                r = pose.rotation
                rotation = [r.w, r.x, r.y, r.z]
            else:
                translation = [0.0, 0.0, 0.0]
                rotation = [1.0, 0.0, 0.0, 0.0]
            camera_intrinsic = None
            if calib_data.camera_config:
                cfg = calib_data.camera_config
                fx, fy, cx, cy = cfg.intrinsic.fx, cfg.intrinsic.fy, cfg.intrinsic.cx, cfg.intrinsic.cy
                camera_intrinsic = [
                    [fx, 0.0, cx],
                    [0.0, fy, cy],
                    [0.0, 0.0, 1.0]
                ]
        except Exception as e:
            self.stats["errors"].append(f"Error processing camera calibration for {camera_name}: {e}")
            translation = [0.0, 0.0, 0.0]
            rotation = [1.0, 0.0, 0.0, 0.0]
            camera_intrinsic = [[1.0, 0.0, 0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]]
        calib_sensor = NuScenesCalibratedSensor(
            token=calib_token,
            sensor_token=sensor_token,
            translation=translation,
            rotation=rotation,
            camera_intrinsic=camera_intrinsic
        )
        self.calibrated_sensors.append(calib_sensor)

    def _normalize_camera_name(self, camera_name: str) -> str:
        """Normalize camera name to NuScenes standard"""
        name_mapping = {
            'front': 'CAM_FRONT',
            'back': 'CAM_BACK', 
            'front_left': 'CAM_FRONT_LEFT',
            'front_right': 'CAM_FRONT_RIGHT',
            'back_left': 'CAM_BACK_LEFT',
            'back_right': 'CAM_BACK_RIGHT'
        }
        
        camera_name_lower = camera_name.lower().replace('camera_', '')
        return name_mapping.get(camera_name_lower, f"CAM_{camera_name.upper()}")
    
    def _process_frames(self, directories: Dict[str, Path]):
        """Process all frames"""
        scene_token = self.scenes[0].token
        
        for i, frame in enumerate(self.project_metadata.frames):
            try:
                self._process_single_frame(frame, scene_token, directories, i)
                self.stats["frames_processed"] += 1
            except Exception as e:
                error_msg = f"Error processing frame {frame.timestamp_ns}: {e}"
                self.stats["errors"].append(error_msg)
    
    def _process_single_frame(
        self, 
        frame: FrameMetadata, 
        scene_token: str, 
        directories: Dict[str, Path],
        frame_index: int
    ):
        """Process a single frame"""
        # Convert timestamp from nanoseconds to microseconds (NuScenes standard)
        timestamp_us = int(frame.timestamp_ns) // 1000
        
        # Generate sample token
        sample_token = generate_sample_token(self.scene_name, frame.timestamp_ns)
        
        # Determine prev/next tokens
        prev_token = ""
        next_token = ""
        if frame_index > 0:
            prev_frame = self.project_metadata.frames[frame_index - 1]
            prev_token = generate_sample_token(self.scene_name, prev_frame.timestamp_ns)
        if frame_index < len(self.project_metadata.frames) - 1:
            next_frame = self.project_metadata.frames[frame_index + 1]
            next_token = generate_sample_token(self.scene_name, next_frame.timestamp_ns)
        
        # Create sample data dictionary to collect sensor data tokens
        sample_data_dict = {}
        
        # Create ego pose
        ego_pose_token = generate_ego_pose_token(self.scene_name, frame.timestamp_ns)
        # Convert Pose model to ego pose dict
        pose = frame.pose
        if pose:
            t = pose.transform.translation
            r = pose.transform.rotation
            ego_pose_data = {
                "translation": [t.x, t.y, t.z],
                "rotation": [r.w, r.x, r.y, r.z]
            }
        else:
            ego_pose_data = {"translation": [0.0,0.0,0.0], "rotation": [1.0,0.0,0.0,0.0]}
        
        ego_pose = NuScenesEgoPose(
            token=ego_pose_token,
            timestamp=timestamp_us,
            rotation=ego_pose_data["rotation"],
            translation=ego_pose_data["translation"]
        )
        self.ego_poses.append(ego_pose)
        
        # Process LIDAR data (main_channel)
        lidar_token = self._process_lidar_data(frame, sample_token, ego_pose_token, directories, timestamp_us)
        if lidar_token:
            sample_data_dict[self.project_metadata.main_channel] = lidar_token
        
        # Process camera data
        if frame.images and isinstance(frame.images, dict):
            camera_tokens = self._process_camera_data(frame, sample_token, ego_pose_token, directories, timestamp_us)
            sample_data_dict.update(camera_tokens)
        
        # Create sample with data
        sample = NuScenesSample(
            token=sample_token,
            timestamp=timestamp_us,
            prev=prev_token,
            next=next_token,
            scene_token=scene_token,
            data=sample_data_dict
        )
        self.samples.append(sample)
        
        # Process annotations
        if frame.annotation:
            self._process_annotations(frame, sample_token, timestamp_us)
    
    def _process_lidar_data(
        self,
        frame: FrameMetadata,
        sample_token: str,
        ego_pose_token: str,
        directories: Dict[str, Path],
        timestamp_us: int
    ) -> Optional[str]:
        main_channel = self.project_metadata.main_channel
        if main_channel not in frame.lidars:
            raise ValueError(f"Missing lidar data for main channel {main_channel} at frame {frame.timestamp_ns}")
        sample_data_token = generate_sample_data_token(self.scene_name, frame.timestamp_ns, main_channel)
        lidar_filename = generate_nuscenes_filename(self.scene_name, main_channel, frame.timestamp_ns, ".pcd")
        lidar_target_path = directories['samples'] / main_channel
        lidar_target_path.mkdir(parents=True, exist_ok=True)
        lidar_source = frame.lidars[main_channel]
        copy_sensor_data(lidar_source, lidar_target_path, lidar_filename)
        sample_data = NuScenesSampleData(
            token=sample_data_token,
            sample_token=sample_token,
            ego_pose_token=ego_pose_token,
            calibrated_sensor_token=self.calibrated_sensor_tokens[main_channel],
            timestamp=timestamp_us,
            fileformat="pcd",
            is_key_frame=True,
            filename=f"samples/{main_channel}/{lidar_filename}"
        )
        self.sample_data.append(sample_data)
        return sample_data_token
    
    def _process_camera_data(
        self,
        frame: FrameMetadata,
        sample_token: str,
        ego_pose_token: str,
        directories: Dict[str, Path],
        timestamp_us: int
    ) -> Dict[str, str]:
        camera_tokens: Dict[str, str] = {}
        if not frame.images:
            return camera_tokens
        for channel, image_url in frame.images.items():
            if channel not in self.calibrated_sensor_tokens:
                raise ValueError(f"Calibration missing for camera channel {channel}")
            sample_data_token = generate_sample_data_token(self.scene_name, frame.timestamp_ns, channel)
            image_filename = generate_nuscenes_filename(self.scene_name, channel, frame.timestamp_ns, ".jpg")
            cam_dir = (directories['samples'] / channel)
            cam_dir.mkdir(parents=True, exist_ok=True)
            if not image_url:
                raise ValueError(f"Missing image URL for channel {channel} frame {frame.timestamp_ns}")
            copy_sensor_data(image_url, cam_dir, image_filename)
            # width/height from calibration
            calib = self.project_metadata.calibration.get(channel)
            height = width = None
            if calib and calib.camera_config:
                height = calib.camera_config.height
                width = calib.camera_config.width
            sample_data = NuScenesSampleData(
                token=sample_data_token,
                sample_token=sample_token,
                ego_pose_token=ego_pose_token,
                calibrated_sensor_token=self.calibrated_sensor_tokens[channel],
                timestamp=timestamp_us,
                fileformat="jpg",
                is_key_frame=True,
                filename=f"samples/{channel}/{image_filename}",
                height=height,
                width=width
            )
            self.sample_data.append(sample_data)
            camera_tokens[channel] = sample_data_token
        return camera_tokens
    
    def _process_annotations(
        self,
        frame: FrameMetadata,
        sample_token: str,
        timestamp_us: int
    ):
        """Process annotations for a frame"""
        if not frame.annotation:
            return
        
        for annotation_item in frame.annotation:
            try:
                # Apply filters
                if not self._should_include_annotation(annotation_item):
                    continue
                
                # Convert annotation
                self._convert_single_annotation(annotation_item, frame, sample_token, timestamp_us)
                self.stats["annotations_converted"] += 1
                
            except Exception as e:
                error_msg = f"Error converting annotation {annotation_item.obj_id}: {e}"
                self.stats["errors"].append(error_msg)
    
    def _should_include_annotation(self, annotation: AnnotationItem) -> bool:
        """Check if annotation should be included based on filters"""
        filter_config = self.export_request.annotation_filter
        
        if not filter_config:
            return True
        
        # Object type filter
        if filter_config.object_types and annotation.obj_type not in filter_config.object_types:
            return False
        
        # Minimum points filter
        if filter_config.min_points and (not annotation.num_pts or annotation.num_pts < filter_config.min_points):
            return False
        
        return True
    
    def _convert_single_annotation(
        self,
        annotation: AnnotationItem,
        frame: FrameMetadata,
        sample_token: str,
        timestamp_us: int
    ):
        """Convert a single annotation to NuScenes format"""
        # Get NuScenes category
        nuscenes_category = get_nuscenes_category(annotation.obj_type)
        category_token = self.category_tokens.get(nuscenes_category)
        
        if not category_token:
            raise ValueError(f"Unknown category: {nuscenes_category}")
        
        # Transform coordinates to global
        ego_pose_dict = None
        if frame.pose:
            t = frame.pose.transform.translation
            r = frame.pose.transform.rotation
            ego_pose_dict = {
                "translation": [t.x, t.y, t.z],
                "rotation": [r.w, r.x, r.y, r.z]
            }
        global_position, global_size_lwh, global_rotation = transform_psr_to_global(
            annotation.psr, ego_pose_dict or {}
        )
        # reorder size from l,w,h -> w,l,h for NuScenes
        global_size = [global_size_lwh[1], global_size_lwh[0], global_size_lwh[2]]
        
        # Validate size
        if not validate_category_size(nuscenes_category, global_size):
            error_msg = f"Invalid size for {nuscenes_category}: {global_size}"
            self.stats["errors"].append(error_msg)
        
        # Get attributes
        default_attrs = get_default_attributes(nuscenes_category)
        attribute_tokens = [self.attribute_tokens[attr] for attr in default_attrs if attr in self.attribute_tokens]
        
        # Generate annotation token
        annotation_token = generate_annotation_token(self.scene_name, frame.timestamp_ns, annotation.obj_id)
        
        # Default visibility (assume full visibility)
        visibility_token = NUSCENES_VISIBILITY["v80-100"]
        
        # Create sample annotation
        sample_annotation = NuScenesSampleAnnotation(
            token=annotation_token,
            sample_token=sample_token,
            instance_token="",  # Will be set by instance tracker
            visibility_token=visibility_token,
            attribute_tokens=attribute_tokens,
            translation=global_position,
            size=global_size,
            rotation=global_rotation,
            prev="",  # Will be set by instance tracker
            next="",  # Will be set by instance tracker
            num_lidar_pts=annotation.num_pts or 0,
            num_radar_pts=0
        )
        
        # Add to instance tracker
        track_id = annotation.obj_id  # Use obj_id as track_id
        instance_token = self.instance_tracker.add_annotation(
            self.scene_name,
            track_id,
            category_token,
            sample_annotation
        )
        
        # Set instance token
        sample_annotation.instance_token = instance_token
    
    def _finalize_annotations(self):
        """Finalize instances and annotations with proper linking"""
        # Get final instances
        instances = self.instance_tracker.finalize_instances()
        self.stats["instances_created"] = len(instances)
        
        # Store instances and annotations
        self.instances = instances
        self.sample_annotations = self.instance_tracker.get_all_annotations()
    
    def _save_json_tables(self, output_dir: Path):
        """Save all JSON tables to files (v1.0-all) with Pydantic validation."""
        # Build pydantic models
        try:
            tables_model = NuScenesTables(
                scene=[SceneModel(**s.to_dict()) for s in self.scenes],
                sample=[SampleModel(**s.to_dict()) for s in self.samples],
                sample_data=[SampleDataModel(**sd.to_dict()) for sd in self.sample_data],
                ego_pose=[EgoPoseModel(**ep.to_dict()) for ep in self.ego_poses],
                sensor=[SensorModel(**se.to_dict()) for se in self.sensors],
                calibrated_sensor=[CalibratedSensorModel(**cs.to_dict()) for cs in self.calibrated_sensors],
                log=[LogModel(**l.to_dict()) for l in self.logs],
                category=[CategoryModel(**c.to_dict()) for c in self.categories],
                attribute=[AttributeModel(**a.to_dict()) for a in self.attributes],
                visibility=[VisibilityModel(**v.to_dict()) for v in self.visibility],
                map=[MapModel(**m.to_dict()) for m in self.maps],
                instance=[InstanceModel(**i.to_dict()) for i in self.instances],
                sample_annotation=[SampleAnnotationModel(**a.to_dict()) for a in self.sample_annotations]
            )
        except Exception as e:
            raise ValueError(f"Schema validation error: {e}")
        cross_errors = cross_validate(tables_model)
        if cross_errors:
            raise ValueError("Cross-table validation errors: \n" + "\n".join(cross_errors))
        tables = {
            "scene.json": [scene.model_dump() for scene in tables_model.scene],
            "sample.json": [sample.model_dump() for sample in tables_model.sample],
            "sample_data.json": [sd.model_dump() for sd in tables_model.sample_data],
            "ego_pose.json": [ep.model_dump() for ep in tables_model.ego_pose],
            "sensor.json": [sensor.model_dump() for sensor in tables_model.sensor],
            "calibrated_sensor.json": [cs.model_dump() for cs in tables_model.calibrated_sensor],
            "log.json": [log.model_dump() for log in tables_model.log],
            "category.json": [cat.model_dump() for cat in tables_model.category],
            "attribute.json": [attr.model_dump() for attr in tables_model.attribute],
            "visibility.json": [vis.model_dump() for vis in tables_model.visibility],
            "map.json": [map_obj.model_dump() for map_obj in tables_model.map],
            "instance.json": [inst.model_dump() for inst in tables_model.instance],
            "sample_annotation.json": [ann.model_dump() for ann in tables_model.sample_annotation]
        }
        for filename, data in tables.items():
            save_json_table(data, output_dir, filename)
