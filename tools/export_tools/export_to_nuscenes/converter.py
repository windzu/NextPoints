"""
Main converter for NextPoints to NuScenes format
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.models.meta_data_model import ProjectMetadataResponse, FrameMetadata
from app.models.export_model import NuScenesExportRequest
from app.models.annotation_model import AnnotationItem

from .schema import (
    NuScenesScene, NuScenesSample, NuScenesSampleData, NuScenesEgoPose,
    NuScenesSensor, NuScenesCalibratedSensor, NuScenesLog, NuScenesCategory,
    NuScenesAttribute, NuScenesVisibility, NuScenesMap, NuScenesInstance,
    NuScenesSampleAnnotation, InstanceTracker
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
        """
        Main conversion method
        
        Args:
            output_dir: Output directory for NuScenes data
            
        Returns:
            Conversion statistics
        """
        try:
            # Create directory structure
            directories = create_nuscenes_directory_structure(output_dir)
            
            # Initialize static data
            self._initialize_static_data()
            
            # Process frames
            self._process_frames(directories)
            
            # Finalize instances and annotations
            self._finalize_annotations()
            
            # Save all JSON tables
            self._save_json_tables(directories['v1.0-trainval'])
            
            # Validate structure
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
        
        # Default map (required by NuScenes SDK)
        map_token = generate_sensor_token(f"map_{self.scene_name}")
        default_map = NuScenesMap(
            token=map_token,
            log_tokens=[log_token],
            category="semantic_prior",
            filename=""
        )
        self.maps.append(default_map)
    
    def _initialize_sensors(self):
        """Initialize sensors from calibration data"""
        calibration = self.project_metadata.calibration
        
        # LIDAR sensor
        lidar_sensor_token = generate_sensor_token("LIDAR_TOP")
        self.sensor_tokens["LIDAR_TOP"] = lidar_sensor_token
        
        lidar_sensor = NuScenesSensor(
            token=lidar_sensor_token,
            channel="LIDAR_TOP",
            modality="lidar"
        )
        self.sensors.append(lidar_sensor)
        
        # LIDAR calibrated sensor (identity transformation)
        lidar_calib_token = generate_calibrated_sensor_token("LIDAR_TOP")
        self.calibrated_sensor_tokens["LIDAR_TOP"] = lidar_calib_token
        
        lidar_calib = NuScenesCalibratedSensor(
            token=lidar_calib_token,
            sensor_token=lidar_sensor_token,
            translation=[0.0, 0.0, 0.0],
            rotation=[1.0, 0.0, 0.0, 0.0]  # Identity quaternion
        )
        self.calibrated_sensors.append(lidar_calib)
        
        # Camera sensors
        for camera_name, calib_data in calibration.items():
            if camera_name.startswith('camera_') or 'camera' in camera_name:
                self._add_camera_sensor(camera_name, calib_data)
    
    def _add_camera_sensor(self, camera_name: str, calib_data: Any):
        """Add camera sensor and calibrated sensor"""
        # Normalize camera name to NuScenes format
        camera_channel = self._normalize_camera_name(camera_name)
        
        # Sensor
        sensor_token = generate_sensor_token(camera_channel)
        self.sensor_tokens[camera_channel] = sensor_token
        
        sensor = NuScenesSensor(
            token=sensor_token,
            channel=camera_channel,
            modality="camera"
        )
        self.sensors.append(sensor)
        
        # Calibrated sensor
        calib_token = generate_calibrated_sensor_token(camera_channel)
        self.calibrated_sensor_tokens[camera_channel] = calib_token
        
        # Extract calibration parameters
        try:
            extrinsic = getattr(calib_data, 'extrinsic', None) or [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
            intrinsic = getattr(calib_data, 'intrinsic', None) or [[1,0,0],[0,1,0],[0,0,1]]
            
            # Convert extrinsic to translation and rotation
            if isinstance(extrinsic, list) and len(extrinsic) >= 12:
                translation = [float(extrinsic[3]), float(extrinsic[7]), float(extrinsic[11])]
            else:
                translation = [0.0, 0.0, 0.0]
            
            # Convert rotation matrix to quaternion (simplified)
            rotation = [1.0, 0.0, 0.0, 0.0]  # Placeholder - should extract from rotation matrix
            
            # Convert intrinsic to 3x3 matrix - simplified handling
            camera_intrinsic: Optional[List[List[float]]] = None
            if intrinsic:
                camera_intrinsic = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]  # Default identity
                
        except Exception as e:
            self.stats["errors"].append(f"Error processing camera calibration for {camera_name}: {e}")
            translation = [0.0, 0.0, 0.0]
            rotation = [1.0, 0.0, 0.0, 0.0]
            camera_intrinsic = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        
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
        ego_pose_data = nuscenes_to_ego_pose_format(frame.pose or {})
        ego_pose_data["timestamp"] = timestamp_us
        
        ego_pose = NuScenesEgoPose(
            token=ego_pose_token,
            timestamp=timestamp_us,
            rotation=ego_pose_data["rotation"],
            translation=ego_pose_data["translation"]
        )
        self.ego_poses.append(ego_pose)
        
        # Process LIDAR data
        lidar_token = self._process_lidar_data(frame, sample_token, ego_pose_token, directories, timestamp_us)
        if lidar_token:
            sample_data_dict["LIDAR_TOP"] = lidar_token
        
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
        """Process LIDAR data for a frame and return sample data token"""
        # Generate sample_data token
        sample_data_token = generate_sample_data_token(self.scene_name, frame.timestamp_ns, "LIDAR_TOP")
        
        # Copy LIDAR file
        lidar_filename = generate_nuscenes_filename(self.scene_name, "LIDAR_TOP", frame.timestamp_ns, ".pcd")
        lidar_target_path = directories['samples_LIDAR_TOP']
        
        # Copy file (placeholder - actual implementation would download from S3)
        copy_sensor_data(frame.pointcloud_url, lidar_target_path, lidar_filename)
        
        # Create sample_data
        sample_data = NuScenesSampleData(
            token=sample_data_token,
            sample_token=sample_token,
            ego_pose_token=ego_pose_token,
            calibrated_sensor_token=self.calibrated_sensor_tokens["LIDAR_TOP"],
            timestamp=timestamp_us,
            fileformat="pcd",
            is_key_frame=True,
            filename=f"samples/LIDAR_TOP/{lidar_filename}"
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
        """Process camera data for a frame and return dict of camera_channel -> sample_data_token"""
        camera_tokens = {}
        
        if not frame.images or not isinstance(frame.images, dict):
            return camera_tokens
            
        for camera_name, image_url in frame.images.items():
            # Normalize camera name
            camera_channel = self._normalize_camera_name(camera_name)
            
            if camera_channel not in self.calibrated_sensor_tokens:
                continue  # Skip if calibration not available
            
            # Generate sample_data token
            sample_data_token = generate_sample_data_token(self.scene_name, frame.timestamp_ns, camera_channel)
            
            # Generate filename
            image_filename = generate_nuscenes_filename(self.scene_name, camera_channel, frame.timestamp_ns, ".jpg")
            camera_target_path = directories.get(f'samples_{camera_channel}')
            
            if camera_target_path:
                # Copy image file
                copy_sensor_data(image_url, camera_target_path, image_filename)
                
                # Create sample_data
                sample_data = NuScenesSampleData(
                    token=sample_data_token,
                    sample_token=sample_token,
                    ego_pose_token=ego_pose_token,
                    calibrated_sensor_token=self.calibrated_sensor_tokens[camera_channel],
                    timestamp=timestamp_us,
                    fileformat="jpg",
                    is_key_frame=True,
                    filename=f"samples/{camera_channel}/{image_filename}",
                    # Note: height and width would be filled from actual image if available
                )
                self.sample_data.append(sample_data)
                camera_tokens[camera_channel] = sample_data_token
        
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
        global_position, global_size, global_rotation = transform_psr_to_global(
            annotation.psr, 
            frame.pose or {}
        )
        
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
        """Save all JSON tables to files"""
        tables = {
            "scene.json": [scene.to_dict() for scene in self.scenes],
            "sample.json": [sample.to_dict() for sample in self.samples],
            "sample_data.json": [sd.to_dict() for sd in self.sample_data],
            "ego_pose.json": [ep.to_dict() for ep in self.ego_poses],
            "sensor.json": [sensor.to_dict() for sensor in self.sensors],
            "calibrated_sensor.json": [cs.to_dict() for cs in self.calibrated_sensors],
            "log.json": [log.to_dict() for log in self.logs],
            "category.json": [cat.to_dict() for cat in self.categories],
            "attribute.json": [attr.to_dict() for attr in self.attributes],
            "visibility.json": [vis.to_dict() for vis in self.visibility],
            "map.json": [map_obj.to_dict() for map_obj in self.maps],
            "instance.json": [inst.to_dict() for inst in self.instances],
            "sample_annotation.json": [ann.to_dict() for ann in self.sample_annotations]
        }
        
        for filename, data in tables.items():
            save_json_table(data, output_dir, filename)
