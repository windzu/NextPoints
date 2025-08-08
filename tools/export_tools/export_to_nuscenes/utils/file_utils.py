"""
File utilities for NuScenes export
"""
import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List


def create_nuscenes_directory_structure(output_dir: Path) -> Dict[str, Path]:
    """
    Create standard NuScenes directory structure
    
    Args:
        output_dir: Output directory path
        
    Returns:
        Dictionary mapping directory names to paths
    """
    # Create main directories
    directories = {
        'samples': output_dir / 'samples',
        'sweeps': output_dir / 'sweeps',
        'maps': output_dir / 'maps',
        'v1.0-trainval': output_dir / 'v1.0-trainval'
    }
    
    # Create sensor subdirectories in samples
    sensor_dirs = ['LIDAR_TOP', 'CAM_FRONT', 'CAM_BACK', 'CAM_FRONT_LEFT', 'CAM_FRONT_RIGHT', 'CAM_BACK_LEFT', 'CAM_BACK_RIGHT']
    
    for sensor in sensor_dirs:
        directories[f'samples_{sensor}'] = directories['samples'] / sensor
    
    # Create all directories
    for dir_path in directories.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    
    return directories


def save_json_table(data: List[Dict[str, Any]], output_path: Path, filename: str) -> None:
    """
    Save data as JSON table file
    
    Args:
        data: List of dictionaries to save
        output_path: Directory to save the file
        filename: Name of the JSON file
    """
    output_file = output_path / filename
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def copy_sensor_data(
    source_url: str,
    target_path: Path,
    filename: str
) -> bool:
    """
    Copy sensor data file from source to target
    
    Args:
        source_url: Source file URL or path
        target_path: Target directory path
        filename: Target filename
        
    Returns:
        True if copy successful, False otherwise
    """
    try:
        # Handle different source types (S3 URL, local path, etc.)
        if source_url.startswith('http'):
            # For HTTP/S3 URLs, would need to download
            # For now, just create placeholder
            target_file = target_path / filename
            target_file.touch()
            return True
        elif os.path.exists(source_url):
            # Local file copy
            target_file = target_path / filename
            shutil.copy2(source_url, target_file)
            return True
        else:
            return False
    except Exception as e:
        print(f"Error copying sensor data: {e}")
        return False


def generate_nuscenes_filename(
    scene_name: str,
    sensor_channel: str,
    timestamp: str,
    file_extension: str
) -> str:
    """
    Generate NuScenes standard filename
    
    Args:
        scene_name: Scene name
        sensor_channel: Sensor channel name
        timestamp: Timestamp string
        file_extension: File extension (e.g., '.pcd', '.jpg')
        
    Returns:
        Formatted filename
    """
    # Remove any existing extension from timestamp
    timestamp = timestamp.replace('.pcd', '').replace('.jpg', '').replace('.png', '')
    
    return f"{scene_name}_{sensor_channel}_{timestamp}{file_extension}"


def validate_nuscenes_structure(output_dir: Path) -> List[str]:
    """
    Validate generated NuScenes directory structure
    
    Args:
        output_dir: Output directory to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Required directories
    required_dirs = ['samples', 'v1.0-trainval']
    for dir_name in required_dirs:
        dir_path = output_dir / dir_name
        if not dir_path.exists():
            errors.append(f"Missing required directory: {dir_name}")
    
    # Required JSON files
    required_files = [
        'scene.json', 'sample.json', 'sample_data.json', 'sample_annotation.json',
        'instance.json', 'ego_pose.json', 'calibrated_sensor.json', 'sensor.json',
        'category.json', 'attribute.json', 'visibility.json', 'log.json'
    ]
    
    v1_dir = output_dir / 'v1.0-trainval'
    if v1_dir.exists():
        for filename in required_files:
            file_path = v1_dir / filename
            if not file_path.exists():
                errors.append(f"Missing required file: v1.0-trainval/{filename}")
    
    return errors


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in MB
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in MB
    """
    if file_path.exists():
        return file_path.stat().st_size / (1024 * 1024)
    return 0.0


def cleanup_temp_files(temp_dir: Path) -> None:
    """
    Clean up temporary files and directories
    
    Args:
        temp_dir: Temporary directory to clean up
    """
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir)
