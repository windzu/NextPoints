# tools/import_tools/custom2nextpoints.py

import os
from app.services.s3_service import S3Service
from app.models.calibration_model import CalibrationMetadata
from tools.utils import find_nearest_timestamp, fuse_pointclouds
from rich import progress


def custom2nextpoints(
    scene_name: str,
    bucket: str,
    s3_service: S3Service,
    main_channel: str,
    time_interval_s: float,
    fusion_lidar: bool = True,
) -> bool:

    custom_prefix = f"{scene_name}/custom"
    nextpoints_prefix = f"{scene_name}/nextpoints"

    # 校验主通道
    if not main_channel:
        raise ValueError("Missing CUSTOM_TO_NEXT_POINTS_MAIN_CHANNEL")

    time_interval_ns = int(time_interval_s * 1e9)

    main_lidar_prefix = f"{custom_prefix}/lidar/{main_channel}"
    lidar_prefix = f"{custom_prefix}/lidar"
    camera_prefix = f"{custom_prefix}/camera"
    ego_pose_prefix = f"{custom_prefix}/ego_pose"
    calib_prefix = f"{custom_prefix}/calib"

    # Step 1: 读取主通道时间戳
    main_files = s3_service.list_objects(bucket, main_lidar_prefix)
    # check main_files is not empty
    if not main_files:
        raise Exception(f"No files found in main channel: {main_lidar_prefix}")
    timestamps = sorted(
        [
            int(os.path.basename(f).split(".")[0])
            for f in main_files
            if f.endswith(".pcd")
        ]
    )
    selected_timestamps = []
    last_ts = None
    for ts in timestamps:
        if last_ts is None or ts - last_ts >= time_interval_ns:
            selected_timestamps.append(ts)
            last_ts = ts

    if not selected_timestamps:
        raise Exception("No timestamps selected from main channel")

    print(f"⌛ Selected {len(selected_timestamps)} timestamps from {main_channel}")

    # Step 2: 获取其他通道的文件列表
    camera_files = s3_service.list_objects(bucket, camera_prefix)
    lidar_files = s3_service.list_objects(bucket, lidar_prefix)
    ego_pose_files = s3_service.list_objects(bucket, ego_pose_prefix)

    # 创建通道时间戳映射
    camera_map, lidar_map, ego_pose_map = {}, {}, {}
    for f in camera_files:
        if f.endswith(".jpg"):
            parts = f.split("/")
            channel = parts[-2]
            ts = int(parts[-1].split(".")[0])
            camera_map.setdefault(channel, {})[ts] = f

    for f in lidar_files:
        if f.endswith(".pcd"):
            parts = f.split("/")
            channel = parts[-2]
            ts = int(parts[-1].split(".")[0])
            lidar_map.setdefault(channel, {})[ts] = f

    for f in ego_pose_files:
        if f.endswith(".json"):
            ts = int(os.path.basename(f).split(".")[0])
            ego_pose_map[ts] = f
    # check camera_map for remove empty channels
    camera_map = {k: v for k, v in camera_map.items() if v}
    lidar_map = {k: v for k, v in lidar_map.items() if v}
    ego_pose_map = {k: v for k, v in ego_pose_map.items() if v}

    # Step 3: upload calibration files
    custom_calib_files = s3_service.list_objects(bucket, calib_prefix)
    for f in custom_calib_files:
        # Note: make sure the file name end with .json
        if not f.endswith(".json"):
            raise ValueError(f"Calibration file {f} is not a JSON file")
        # get the channel from the file name
        channel = os.path.basename(f).split(".")[0]
        if channel not in lidar_map and channel not in camera_map:
            print(f"⚠️ Skipping calibration file for missing channel: {channel}")
            continue

        # edit the file name to match nextpoints format
        print(f"Processing calibration file: {f}")
        calib_info = s3_service.read_json_object(bucket, f)
        if channel.startswith("lidar"):
            calib_info["sensor_type"] = "lidar"
        elif channel.startswith("cam"):
            calib_info["sensor_type"] = "camera"
        else:
            raise ValueError(f"Unknown channel type in calibration file: {channel}")

        # use model validation to ensure the calibration data is valid
        CalibrationMetadata.model_validate(calib_info)

        if calib_info["sensor_type"] == "lidar" and fusion_lidar:
            print(f"⚠️ Skipping lidar calibration for fusion: {channel}")
            continue

        # upload the calibration file to nextpoints prefix
        dst_key = f"{nextpoints_prefix}/calib/{channel}.json"
        s3_service.upload_json_object(bucket, dst_key, calib_info)

    if fusion_lidar:
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
    lidar_channels = list(lidar_map.keys())
    camera_channels = list(camera_map.keys())
    nextpoints_calib_files = s3_service.list_objects(
        bucket, f"{nextpoints_prefix}/calib"
    )

    calib_params = {}
    for f in nextpoints_calib_files:
        if f.endswith(".json"):
            channel = os.path.basename(f).split(".")[0]
            print(f"Loading calibration file for channel {channel}: {f}")
            calib_params[channel] = s3_service.read_json_object(bucket, f)

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
        dst = f"{nextpoints_prefix}/ego_pose/{ts}.json"
        s3_service.copy_object(bucket, src, bucket, dst)

        # === 融合点云 ===
        if fusion_lidar:
            lidar_objs = []
            for ch in lidar_channels:
                nearest_ts = find_nearest_timestamp(ts, list(lidar_map[ch].keys()))
                src_key = lidar_map[ch][nearest_ts]
                obj_data = s3_service.get_object(bucket, src_key)
                ignore_areas = calib_params.get(ch, {}).get("ignore_areas", [])
                lidar_objs.append((ch, obj_data, ignore_areas))

            fusion_pcd = fuse_pointclouds(lidar_objs)
            dst_key = f"{nextpoints_prefix}/lidar/lidar-fusion/{ts}.pcd"
            s3_service.put_object(bucket, dst_key, fusion_pcd)

    print(f"✅ Finished converting {scene_name} to nextpoints")
    return True
