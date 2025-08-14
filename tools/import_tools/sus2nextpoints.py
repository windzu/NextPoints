# tools/import_tools/sus2nextpoints.py

import os
from scipy.spatial.transform import Rotation as R
from rich import progress
from copy import deepcopy
from typing import List, Dict, Any, Optional

from app.services.s3_service import S3Service
from app.models.calibration_model import CalibrationMetadata
from app.models.annotation_model import AnnotationItem
from app.models.base_model import Pose
from tools.utils import find_nearest_timestamp


def sus2nextpoints(
    scene_name: str,
    bucket: str,
    s3_service: S3Service,
) -> bool:
    """将SUS格式转换为NextPoints格式

    sus dir structure:
    - scene_name/sus/
        - lidar/
            - lidar_0000000000.pcd
            - lidar_0000001000.pcd
        - camera/
            - cam000/
                - lidar_0000000000.jpg
                - lidar_0000001000.jpg
            - cam001/
                - lidar_0000000000.jpg
                - lidar_0000001000.jpg
        - ego_pose/
            - lidar_0000000000.json
            - lidar_0000001000.json
        - calib/
            - camera/
                - cam000.json
                - cam001.json
        - label/
            - lidar_0000000000.json
            - lidar_0000001000.json

    """

    sus_prefix = f"{scene_name}/sus"
    nextpoints_prefix = f"{scene_name}/nextpoints"

    lidar_channel = "lidar-fusion"

    lidar_prefix = f"{sus_prefix}/lidar"
    camera_prefix = f"{sus_prefix}/camera"
    ego_pose_prefix = f"{sus_prefix}/ego_pose"
    label_prefix = f"{sus_prefix}/label"

    # Step 1: 读取主通道时间戳
    lidar_files = s3_service.list_objects(bucket, lidar_prefix)
    # check main_files is not empty
    if not lidar_files:
        raise Exception(f"No lidar files found in : {lidar_prefix}")
    timestamps = []
    for f in lidar_files:
        if f.endswith(".pcd"):
            # get the timestamp from the file name
            ts = int(os.path.basename(f).split(".")[0].split("_")[-1])
            timestamps.append(ts)
    timestamps = sorted(timestamps)
    if not timestamps:
        raise Exception(f"No valid timestamps found in lidar channel: {lidar_prefix}")

    # Note : choose all timestamps
    selected_timestamps = timestamps

    if not selected_timestamps:
        raise Exception("No timestamps selected from main channel")

    print(f"⌛ Selected {len(selected_timestamps)} timestamps from lidar ")

    # Step 2: 获取其他通道的文件列表
    camera_files = s3_service.list_objects(bucket, camera_prefix)
    lidar_files = s3_service.list_objects(bucket, lidar_prefix)
    ego_pose_files = s3_service.list_objects(bucket, ego_pose_prefix)
    label_files = s3_service.list_objects(bucket, label_prefix)

    # 创建通道时间戳映射
    camera_map, lidar_map, ego_pose_map, label_map = {}, {}, {}, {}
    for f in camera_files:
        if f.endswith(".jpg"):
            parts = f.split("/")
            channel = parts[-2]
            ts = int(parts[-1].split(".")[0].split("_")[-1])
            camera_map.setdefault(channel, {})[ts] = f

    for f in lidar_files:
        if f.endswith(".pcd"):
            ts = int(os.path.basename(f).split(".")[0].split("_")[-1])
            lidar_map.setdefault(lidar_channel, {})[ts] = f

    for f in ego_pose_files:
        if f.endswith(".json"):
            ts = int(os.path.basename(f).split(".")[0].split("_")[-1])
            ego_pose_map[ts] = f

    for f in label_files:
        if f.endswith(".json"):
            ts = int(os.path.basename(f).split(".")[0].split("_")[-1])
            label_map[ts] = f

    # check camera_map for remove empty channels
    camera_map = {k: v for k, v in camera_map.items() if v}
    lidar_map = {k: v for k, v in lidar_map.items() if v}
    ego_pose_map = {k: v for k, v in ego_pose_map.items() if v}
    label_map = {k: v for k, v in label_map.items() if v}

    # Step 3: upload calibration files
    # - build fake camera calibration info
    for channel in camera_map:
        if channel.startswith("cam"):
            # read the first camera file to get the width and height
            first_file = next(iter(camera_map[channel].values()))
            first_image = s3_service.read_image_object(bucket, first_file)
            height, width = first_image.shape[:2]

            calib_info = {
                "channel": channel,
                "sensor_type": "camera",
                "pose": {
                    "parent_frame_id": "base_link",
                    "child_frame_id": channel,
                    "transform": {
                        "translation": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                },
                "camera_config": {
                    "width": width,
                    "height": height,
                    "model": "pinhole",
                    "intrinsic": {
                        "fx": width,
                        "fy": height,
                        "cx": width / 2,
                        "cy": height / 2,
                        "skew": 0.0,
                    },
                    "distortion_coefficients": {
                        "k1": 0.0,
                        "k2": 0.0,
                        "p1": 0.0,
                        "p2": 0.0,
                    },
                },
                "ignore_areas": [],
            }
        else:
            raise ValueError(f"Unknown channel type: {channel}")

        CalibrationMetadata.model_validate(calib_info)

        # upload the calibration file to nextpoints prefix
        dst_key = f"{nextpoints_prefix}/calib/{channel}.json"
        s3_service.upload_json_object(bucket, dst_key, calib_info)

    # - build fake lidar-fusion calibration info
    print("🔄 Fusion lidar enabled, upload lidar-fusion calib file.")
    # upload a dummy calibration file for lidar fusion
    fusion_calib = {
        "channel": "lidar-fusion",
        "sensor_type": "lidar",
        "pose": {
            "parent_frame_id": "base_link",
            "child_frame_id": "lidar-fusion",
            "transform": {
                "translation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
            },
        },
        "ignore_areas": [],
    }

    CalibrationMetadata.model_validate(fusion_calib)
    dst_key = f"{nextpoints_prefix}/calib/lidar-fusion.json"
    s3_service.upload_json_object(bucket, dst_key, fusion_calib)

    # Step 4: 遍历采样时间戳，做同步拷贝
    camera_channels = list(camera_map.keys())
    for ts in progress.track(selected_timestamps):
        # === 拷贝相机 ===
        for cam in camera_channels:
            nearest_ts = find_nearest_timestamp(ts, list(camera_map[cam].keys()))
            src = camera_map[cam][nearest_ts]
            dst = f"{nextpoints_prefix}/camera/{cam}/{ts}.jpg"
            s3_service.copy_object(bucket, src, bucket, dst)

        # === 拷贝 ego_pose ===
        nearest_ego_ts = find_nearest_timestamp(ts, list(ego_pose_map.keys()))
        src = ego_pose_map[nearest_ego_ts]
        if not src:
            raise ValueError(f"No ego pose found for timestamp {ts}")
        # convert ego pose to nextpoints format
        sus_ego_pose_data = s3_service.read_json_object(bucket, src)
        if not isinstance(sus_ego_pose_data, Dict):
            raise ValueError(f"Invalid ego pose data format in {src}")
        nextpoints_ego_pose_data = {
            "parent_frame_id": "map",
            "child_frame_id": "base_link",
            "transform": {
                "translation": {
                    "x": float(sus_ego_pose_data["translation"][0]),
                    "y": float(sus_ego_pose_data["translation"][1]),
                    "z": float(sus_ego_pose_data["translation"][2]),
                },
                "rotation": {
                    "x": float(sus_ego_pose_data["rotation"][0]),
                    "y": float(sus_ego_pose_data["rotation"][1]),
                    "z": float(sus_ego_pose_data["rotation"][2]),
                    "w": float(sus_ego_pose_data["rotation"][3]),
                },
            },
        }
        Pose.model_validate(nextpoints_ego_pose_data)
        # upload the ego pose data to nextpoints prefix
        dst = f"{nextpoints_prefix}/ego_pose/{ts}.json"
        s3_service.upload_json_object(bucket, dst, nextpoints_ego_pose_data)

        # s3_service.copy_object(bucket, src, bucket, dst)

        # === 拷贝 lidar ===
        nearest_lidar_ts = find_nearest_timestamp(
            ts, list(lidar_map[lidar_channel].keys())
        )
        src = lidar_map[lidar_channel][nearest_lidar_ts]
        dst = f"{nextpoints_prefix}/lidar/{lidar_channel}/{ts}.pcd"
        s3_service.copy_object(bucket, src, bucket, dst)

        # === 拷贝 label ===
        nearest_label_ts = find_nearest_timestamp(ts, list(label_map.keys()))
        if nearest_label_ts is not None:
            src = label_map[nearest_label_ts]
            sus_label_list = s3_service.read_json_object(bucket, src)
            if not isinstance(sus_label_list, List):
                raise ValueError(f"Label file {src} is not a list")
            nextpoints_label_list = []
            for sus_anno in sus_label_list:
                nextpoints_anno = deepcopy(sus_anno)

                # convert rotation from euler to quaternion
                rotation_euler = sus_anno["psr"]["rotation"]
                angles = [rotation_euler["x"], rotation_euler["y"], rotation_euler["z"]]
                quat = R.from_euler("xyz", angles, degrees=False).as_quat()
                nextpoints_anno["psr"]["rotation"] = {
                    "x": float(quat[0]),
                    "y": float(quat[1]),
                    "z": float(quat[2]),
                    "w": float(quat[3]),
                }

                # check if have "num_lidar_pts" key
                if "num_lidar_pts" in nextpoints_anno:
                    nextpoints_anno["num_pts"] = int(nextpoints_anno["num_lidar_pts"])
                    # remove the old key
                    del nextpoints_anno["num_lidar_pts"]

                # use pydantic to check the annotation format
                AnnotationItem.model_validate(nextpoints_anno)
                nextpoints_label_list.append(nextpoints_anno)
            # convert label to nextpoints format
            dst = f"{nextpoints_prefix}/label/{ts}.json"
            s3_service.upload_json_object(bucket, dst, nextpoints_label_list)

    print(f"✅ Finished converting {scene_name} to nextpoints")
    return True
