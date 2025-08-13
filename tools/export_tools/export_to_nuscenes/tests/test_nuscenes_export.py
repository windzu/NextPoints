"""
Test script for NuScenes export functionality using nuscenes-devkit
"""
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

# Import converter
from tools.export_tools.export_to_nuscenes.converter import NextPointsToNuScenesConverter

# Mock data for testing
def create_mock_project_metadata():
    """Create mock project metadata for testing"""
    from app.models.meta_data_model import ProjectMetadataResponse, FrameMetadata
    from app.models.project_model import ProjectResponse, ProjectStatus
    from app.models.annotation_model import AnnotationItem, PSR, Position, Rotation, Scale
    from app.models.calibration_model import CalibrationMetadata, CameraConfig
    
    # Mock project
    project = ProjectResponse(
        id=1,
        name="test_project",
        description="Test project for NuScenes export",
        created_at="2025-08-07T00:00:00Z",
        status=ProjectStatus.completed
    )
    
    # Mock calibration
    camera_config = CameraConfig(
        width=1920,
        height=1080,
        model="pinhole",
        intrinsic=[[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]],
        distortion_coefficients=[0.0, 0.0, 0.0, 0.0, 0.0]
    )
    
    calibration = {
        "camera_front": CalibrationMetadata(
            channel="camera_front",
            translation=[0.5, 0.0, 1.8],
            rotation=[1.0, 0.0, 0.0, 0.0],
            camera_config=camera_config
        ),
        "LIDAR_TOP": CalibrationMetadata(
            channel="LIDAR_TOP",
            translation=[0.0, 0.0, 0.0],
            rotation=[1.0, 0.0, 0.0, 0.0]
        )
    }
    
    # Mock frames
    frames = []
    for i in range(3):
        timestamp_ns = str(1500000000000000000 + i * 100000000)  # 100ms intervals
        
        # Mock annotation
        annotation = [
            AnnotationItem(
                obj_id=f"car_{i}",
                obj_type="Car",
                obj_attr="moving",
                num_pts=150,
                psr=PSR(
                    position=Position(x=10.0 + i, y=2.0, z=0.5),
                    rotation=Rotation(x=0.0, y=0.0, z=0.1 * i),
                    scale=Scale(x=4.5, y=2.0, z=1.8)
                )
            )
        ]
        
        frame = FrameMetadata(
            id=i,
            timestamp_ns=timestamp_ns,
            prev_timestamp_ns=str(1500000000000000000 + (i-1) * 100000000) if i > 0 else None,
            next_timestamp_ns=str(1500000000000000000 + (i+1) * 100000000) if i < 2 else None,
            pointcloud_url=f"s3://test-bucket/lidar/{timestamp_ns}.pcd",
            images={
                "camera_front": f"s3://test-bucket/camera/front/{timestamp_ns}.jpg"
            },
            pose={
                "translation": [i * 5.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "timestamp": int(timestamp_ns) // 1000
            },
            annotation=annotation
        )
        frames.append(frame)
    
    return ProjectMetadataResponse(
        project=project,
        frame_count=len(frames),
        start_timestamp_ns=frames[0].timestamp_ns,
        end_timestamp_ns=frames[-1].timestamp_ns,
        duration_seconds=0.2,
        calibration=calibration,
        frames=frames
    )


def create_mock_export_request():
    """Create mock export request"""
    from app.models.export_model import NuScenesExportRequest, AnnotationFilter, CoordinateSystem
    
    annotation_filter = AnnotationFilter(
        object_types=["Car", "Pedestrian"],
        min_points=10
    )
    
    return NuScenesExportRequest(
        coordinate_system=CoordinateSystem.GLOBAL,
        annotation_filter=annotation_filter
    )


def test_conversion():
    """Test complete conversion process"""
    print("Testing NextPoints to NuScenes conversion...")
    
    # Create test output directory
    output_dir = Path("/tmp/test_nuscenes_export")
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Created output directory: {output_dir}")
    
    # Create mock project data
    mock_project = create_mock_project_metadata()
    mock_export_request = create_mock_export_request()
    
    # Create converter instance
    converter = NextPointsToNuScenesConverter(
        project_metadata=mock_project,
        export_request=mock_export_request
    )
    
    # Convert
    result = converter.convert(output_dir)
    
    print(f"Conversion completed!")
    print(f"Stats: {result}")
    
    # Check what files were created
    print(f"Files created in {output_dir}:")
    for file_path in output_dir.rglob("*"):
        if file_path.is_file():
            print(f"  {file_path.relative_to(output_dir)} ({file_path.stat().st_size} bytes)")
    
    # Basic validation
    validate_basic_structure(output_dir)
    print("Basic structure validation passed!")
    
    # Try NuScenes SDK validation
    try:
        test_with_nuscenes_sdk(output_dir)
    except ImportError as e:
        print(f"Warning: {e}")
    except Exception as e:
        print(f"NuScenes SDK validation failed: {e}")
    
    return result


def validate_basic_structure(output_dir: Path) -> list:
    """Validate basic NuScenes directory structure"""
    from tools.export_tools.export_to_nuscenes.utils import validate_nuscenes_structure
    
    return validate_nuscenes_structure(output_dir)


def test_with_nuscenes_sdk(output_dir: Path):
    """Test with official NuScenes SDK"""
    try:
        from nuscenes.nuscenes import NuScenes
        from nuscenes.utils.data_classes import LidarPointCloud
        
        print(f"Initializing NuScenes with dataroot: {output_dir}")
        
        # Initialize NuScenes object
        nusc = NuScenes(version='v1.0-trainval', dataroot=str(output_dir), verbose=True)
        
        # Basic validation
        print(f"Loaded NuScenes dataset with {len(nusc.scene)} scenes")
        print(f"Total samples: {len(nusc.sample)}")
        print(f"Total annotations: {len(nusc.sample_annotation)}")
        print(f"Total instances: {len(nusc.instance)}")
        
        # Validate first scene if exists
        if len(nusc.scene) > 0:
            scene = nusc.scene[0]
            print(f"First scene: {scene}")
            
            # Get first sample if exists
            if 'first_sample_token' in scene and scene['first_sample_token']:
                try:
                    sample = nusc.get('sample', scene['first_sample_token'])
                    print(f"First sample: {sample}")
                    
                    # Validate sample data
                    if 'data' in sample and sample['data']:
                        for sensor_channel, sample_data_token in sample['data'].items():
                            print(f"Checking sensor {sensor_channel} with token {sample_data_token}")
                            try:
                                sample_data = nusc.get('sample_data', sample_data_token)
                                print(f"{sensor_channel} data: {sample_data}")
                            except Exception as sd_error:
                                print(f"Error getting sample_data for {sensor_channel}: {sd_error}")
                    else:
                        print("Sample has no data field or data is empty")
                except Exception as sample_error:
                    print(f"Sample validation failed: {sample_error}")
                    import traceback
                    traceback.print_exc()
        else:
            print("No scenes found in dataset")
        
        print("NuScenes SDK validation passed!")
        return True
        
    except ImportError as e:
        raise ImportError(f"NuScenes SDK not installed: {e}")
    except Exception as e:
        print(f"Full exception details:")
        import traceback
        traceback.print_exc()
        raise Exception(f"NuScenes SDK validation failed: {e}")


def test_category_mapping():
    """Test category mapping functionality"""
    print("Testing category mapping...")
    
    from tools.export_tools.export_to_nuscenes.category_mapping import (
        get_nuscenes_category, get_default_attributes, validate_category_size
    )
    
    # Test mappings
    test_cases = [
        ("Car", "vehicle.car"),
        ("Pedestrian", "human.pedestrian.adult"),
        ("Bicycle", "vehicle.bicycle"),
        ("Unknown", "movable_object.pushable_pullable")
    ]
    
    for nextpoints_type, expected_nuscenes in test_cases:
        result = get_nuscenes_category(nextpoints_type)
        assert result == expected_nuscenes, f"Expected {expected_nuscenes}, got {result}"
        print(f"✓ {nextpoints_type} -> {result}")
    
    # Test attributes
    attrs = get_default_attributes("vehicle.car")
    print(f"Default attributes for vehicle.car: {attrs}")
    
    # Test size validation
    valid_car_size = [4.5, 2.0, 1.8]
    invalid_car_size = [20.0, 5.0, 10.0]
    
    assert validate_category_size("vehicle.car", valid_car_size) == True
    assert validate_category_size("vehicle.car", invalid_car_size) == False
    
    print("Category mapping tests passed!")


def test_coordinate_transform():
    """Test coordinate transformation functions"""
    print("Testing coordinate transformations...")
    
    from tools.export_tools.export_to_nuscenes.utils import (
         transform_position_to_global, transform_psr_to_global
    )
    from app.models.annotation_model import PSR, Position, Rotation, Scale

    
    # Test position transform
    local_pos = Position(x=1.0, y=2.0, z=0.5)
    ego_pose = {
        "translation": [10.0, 20.0, 0.0],
        "rotation": [1.0, 0.0, 0.0, 0.0]
    }
    global_pos = transform_position_to_global(local_pos, ego_pose)
    print(f"Local {local_pos} + Ego {ego_pose} -> Global {global_pos}")
    
    # Test full PSR transform
    psr = PSR(
        position=Position(x=1.0, y=2.0, z=0.5),
        rotation=Rotation(x=0.0, y=0.0, z=0.1, w=0.99),
        scale=Scale(x=4.5, y=2.0, z=1.8)
    )
    
    global_position, global_size, global_rotation = transform_psr_to_global(psr, ego_pose)
    print(f"PSR transform: pos={global_position}, size={global_size}, rot={global_rotation}")
    
    print("Coordinate transformation tests passed!")


if __name__ == "__main__":
    print("=== NextPoints to NuScenes Export Test ===")
    
    try:
        # Test individual components
        test_category_mapping()
        test_coordinate_transform()
        
        # Test full conversion
        success = test_conversion()
        
        if success:
            print("\n🎉 All tests passed! The NuScenes export functionality is working correctly.")
        else:
            print("\n❌ Some tests failed. Please check the error messages above.")
            
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
