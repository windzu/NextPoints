"""
File utilities for NuScenes export
"""
import os
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional


def create_nuscenes_directory_structure(output_dir: Path, sensor_channels: Optional[List[str]] = None) -> Dict[str, Path]:
    """Create directory structure (v1.0-all). Optional dynamic sensor channel subdirs.
    
    Args:
        output_dir: base output path
        sensor_channels: list of channel names to create under samples/
        
    Returns:
        mapping of logical names to paths
    """
    directories: Dict[str, Path] = {
        'samples': output_dir / 'samples',
        'sweeps': output_dir / 'sweeps',
        'maps': output_dir / 'maps',
        'v1.0-all': output_dir / 'v1.0-all'
    }
    
    # Create main directories
    for dir_path in directories.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Create sensor subdirectories in samples if provided
    if sensor_channels:
        for ch in sensor_channels:
            ch_dir = directories['samples'] / ch
            ch_dir.mkdir(parents=True, exist_ok=True)
            directories[f'samples_{ch}'] = ch_dir
    
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
    """Copy/download sensor data file. Raises on failure per strict policy."""
    try:
        target_file = target_path / filename
        if source_url.startswith('http://') or source_url.startswith('https://'):
            # Download remote (presigned) resource
            urllib.request.urlretrieve(source_url, target_file)
            return True
        elif os.path.exists(source_url):
            shutil.copy2(source_url, target_file)
            return True
        else:
            raise ValueError(f"Unsupported or missing source path: {source_url}")
    except Exception as e:
        raise ValueError(f"Failed to copy sensor data from {source_url} -> {filename}: {e}")


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


def validate_nuscenes_structure(output_dir: Path, main_channel: Optional[str] = None) -> List[str]:
    """Validate generated NuScenes directory structure and file presence.
    Checks:
      - Required directories & JSON files.
      - Each sample_data entry's filename exists.
      - At least one point cloud (pcd) file present (optionally in main_channel).
    """
    errors: List[str] = []
    required_dirs = ['samples', 'v1.0-all']
    for dir_name in required_dirs:
        if not (output_dir / dir_name).exists():
            errors.append(f"Missing required directory: {dir_name}")
    required_files = [
        'scene.json', 'sample.json', 'sample_data.json', 'sample_annotation.json',
        'instance.json', 'ego_pose.json', 'calibrated_sensor.json', 'sensor.json',
        'category.json', 'attribute.json', 'visibility.json', 'log.json', 'map.json'
    ]
    v1_dir = output_dir / 'v1.0-all'
    if v1_dir.exists():
        for filename in required_files:
            if not (v1_dir / filename).exists():
                errors.append(f"Missing required file: v1.0-all/{filename}")
    # Load sample_data and verify referenced files
    pcd_count = 0
    if (v1_dir / 'sample_data.json').exists():
        try:
            with open(v1_dir / 'sample_data.json', 'r', encoding='utf-8') as f:
                sd_list = json.load(f)
            for entry in sd_list:
                rel = entry.get('filename')
                if not rel:
                    errors.append(f"sample_data {entry.get('token')} missing filename")
                    continue
                file_path = output_dir / rel
                if not file_path.exists():
                    errors.append(f"Referenced data file missing: {rel}")
                if entry.get('fileformat') == 'pcd':
                    if (not main_channel) or (main_channel and main_channel in rel):
                        pcd_count += 1
        except Exception as e:
            errors.append(f"Failed to inspect sample_data.json: {e}")
    if pcd_count == 0:
        errors.append("No point cloud files found for main channel" + (f" {main_channel}" if main_channel else ""))
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
