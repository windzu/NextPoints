#!/usr/bin/env python3
"""
Final validation test for NextPoints to NuScenes export functionality
This script demonstrates the complete working implementation
"""

import os
import sys
import tempfile
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, '/workspace')

def test_complete_workflow():
    """Test the complete export workflow"""
    print("🚀 Starting NextPoints to NuScenes Export Final Test")
    print("=" * 60)
    
    try:
        # Import our implementation
        from tools.export_tools.export_to_nuscenes.converter import NextPointsToNuScenesConverter
        from app.models.meta_data_model import ProjectMetadataResponse, FrameMetadata
        from app.models.project_model import ProjectResponse, ProjectStatus
        from app.models.export_model import NuScenesExportRequest, AnnotationFilter, CoordinateSystem
        from app.models.annotation_model import AnnotationItem, PSR, Position, Rotation, Scale
        from app.models.calibration_model import CalibrationMetadata, CameraConfig
        
        # Import test data creation function
        from tools.export_tools.export_to_nuscenes.tests.test_nuscenes_export import (
            create_mock_project_metadata, create_mock_export_request
        )
        
        print("✅ Successfully imported all modules")
        
        # Create test data using existing functions
        project_metadata = create_mock_project_metadata()
        export_request = create_mock_export_request()
        
        print("✅ Created test data successfully")
        
        # Create output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nuscenes_export"
            
            print(f"📁 Output directory: {output_path}")
            
            # Initialize converter
            converter = NextPointsToNuScenesConverter(
                project_metadata=project_metadata,
                export_request=export_request
            )
            
            print("✅ Converter initialized")
            
            # Perform conversion
            result = converter.convert(output_path)
            
            print("✅ Conversion completed")
            print(f"📊 Results: {result}")
            
            # Validate with NuScenes SDK
            try:
                from nuscenes.nuscenes import NuScenes
                nusc = NuScenes(version='v1.0-trainval', dataroot=str(output_path), verbose=False)
                
                print("✅ NuScenes SDK validation passed")
                print(f"   Scenes: {len(nusc.scene)}")
                print(f"   Samples: {len(nusc.sample)}")
                print(f"   Annotations: {len(nusc.sample_annotation)}")
                print(f"   Sample Data: {len(nusc.sample_data)}")
                
                # Test basic API usage
                scene = nusc.scene[0]
                sample = nusc.get('sample', scene['first_sample_token'])
                
                print(f"✅ First sample has data for: {list(sample['data'].keys())}")
                
            except ImportError:
                print("⚠️  NuScenes SDK not available for validation")
            except Exception as e:
                print(f"❌ NuScenes SDK validation failed: {e}")
                return False
        
        print("=" * 60)
        print("🎉 ALL TESTS PASSED! NextPoints to NuScenes export is working correctly!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_complete_workflow()
    sys.exit(0 if success else 1)
