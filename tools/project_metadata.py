from sqlmodel import Session
from fastapi import HTTPException, Depends, status
import posixpath
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Tuple
from botocore.exceptions import ClientError
from sqlmodel import select
import os
from nextpoints_sdk.models.project_metadata import (
    ProjectMetadataResponse,
    FrameMetadata,
)
from nextpoints_sdk.models.calibration import CalibrationMetadata
from nextpoints_sdk.models.pose import Pose
from nextpoints_sdk.models.annotation import AnnotationItem

from app.services.s3_service import S3Service
from app.models.project_model import Project, ProjectResponse, ProjectStatus


from app.database import get_session


def get_project_metadata(
    project_name: str,
    session: Session = Depends(get_session),
    use_presigned_urls: bool = True,
) -> ProjectMetadataResponse:
    """
    获取项目完整元数据,用于对数据进行校验
    """
    # 1. 获取项目基本信息和状态
    project = session.exec(select(Project).where(Project.name == project_name)).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. 初始化S3服务
    s3_service = S3Service(
        access_key_id=project.access_key_id,
        secret_access_key=project.secret_access_key,
        endpoint_url=project.s3_endpoint,
        region_name=project.region_name,
    )

    # 3. generate project metadata
    try:
        project_meta_data = _generate_project_meta_data(
            project, s3_service, use_presigned_urls
        )
        return project_meta_data
    except Exception as e:
        # 捕获生成 meta.json 时的任何异常
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate_project_meta_data: {str(e)}",
        )


def _generate_project_meta_data(
    project: Project,
    s3_service: S3Service,
    use_presigned_urls: bool,
    main_channel: Optional[str] = "lidar-fusion",
) -> ProjectMetadataResponse:
    """
    目录约定（均在 root = bucket_prefix 下）：
      - calib/<channel>.json
      - lidar/<lidar_channel>/<timestamp>.pcd
      - camera/<camera_channel>/<timestamp>.jpg
      - ego_pose/<timestamp>.json
    """

    def _safe_join(*parts: str, strip_slash=True) -> str:
        """
        安全拼接 POSIX 风格路径，自动去除空值和多余斜杠。

        Args:
            *parts: 路径片段（可以包含空字符串或 None）
            strip_slash: 是否去掉每个片段的首尾斜杠（默认 True）

        Returns:
            拼接后的路径字符串
        """
        cleaned_parts = []
        for p in parts:
            if not p:  # 过滤 None / 空字符串
                continue
            if strip_slash:
                p = p.strip("/")  # 去掉首尾斜杠，避免重复
            cleaned_parts.append(p)

        return posixpath.join(*cleaned_parts)

    def _stem(filename: str) -> str:
        """返回去扩展名后的文件名"""
        base = filename.rsplit("/", 1)[-1]
        return base.rsplit(".", 1)[0] if "." in base else base

    def _is_ext(key: str, *exts: str) -> bool:
        k = key.lower()
        return any(k.endswith(e.lower()) for e in exts)

    def _ns_to_int(ts_ns: str) -> int:
        return int(ts_ns)

    def _project_to_response(project: Project) -> ProjectResponse:
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=ProjectStatus(project.status),
            created_at=project.created_at.isoformat(),
        )

    def _as_key(s3: S3Service, project: Project, bucket_key: str) -> str:
        """将 S3 对象键转换为项目内的相对路径"""
        return bucket_key

    def _as_url(s3: S3Service, project: Project, bucket_key: str) -> str:
        """如需 URL,可用该函数替换 _as_key 的调用"""
        return s3.get_object_url(
            bucket_name=project.bucket_name,
            object_key=bucket_key,
            use_presigned=project.use_presigned_urls,
            expiration=project.expiration_minutes * 60,
        )

    def _check_camera_channel_and_camera_calibration(
        camera_channels: Dict[str, Set[str]],
        calibration: Dict[str, CalibrationMetadata],
    ) -> None:
        """
        校验 camera_channels 和 calibration 的一致性
        - camera_channels 中的通道必须在 calibration 中存在,且必须有 camera_config
        - calibration 中的 camera calibration 如果不在 camera_channels 中，则忽略
        """
        for channel in list(camera_channels.keys()):
            if channel not in calibration:
                raise ValueError(
                    f"Camera channel '{channel}' not found in calibration metadata."
                )
            if calibration[channel].camera_config is None:
                raise ValueError(
                    f"Camera channel '{channel}' in calibration metadata must have a camera_config."
                )

        for channel in list(calibration.keys()):
            if (
                calibration[channel].camera_config is not None
                and channel not in camera_channels
            ):
                del calibration[channel]

    bucket = project.bucket_name
    root = _safe_join(project.bucket_prefix or "")

    calib_prefix = _safe_join(root, "calib")
    lidar_prefix = _safe_join(root, "lidar")
    camera_prefix = _safe_join(root, "camera")
    ego_pose_prefix = _safe_join(root, "ego_pose")

    # 1) 读 calib：严格校验为 CalibrationMetadata
    calibration: Dict[str, CalibrationMetadata] = {}
    for obj in s3_service.list_all_objects(bucket, calib_prefix):
        key = obj.get("Key") or obj.get("key")
        if not key or not _is_ext(key, ".json"):
            continue
        raw = s3_service.read_json_object(bucket, key)
        meta = CalibrationMetadata.model_validate(raw)  # 不一致直接抛错
        chan = meta.channel or _stem(key)  # 以 JSON 内 channel 为准，缺失则用文件名
        # 防止重复
        if chan in calibration:
            raise ValueError(f"重复的 calibration channel: {chan}")
        calibration[chan] = meta

    # 2) 枚举 lidar/camera 子通道及各自的时间戳索引
    lidar_channels: Dict[str, Set[str]] = {}  # channel -> {timestamp_ns}
    lidar_index: Dict[Tuple[str, str], str] = {}  # (channel, ts) -> key

    for obj in s3_service.list_all_objects(bucket, lidar_prefix):
        key = obj.get("Key") or obj.get("key")
        if not key or not _is_ext(key, ".pcd"):
            continue
        # 结构：lidar/<channel>/<timestamp>.pcd
        rel = key[len(lidar_prefix) :].lstrip("/")  # <channel>/<file>
        if "/" not in rel:
            # 忽略不规范
            continue
        channel, fname = rel.split("/", 1)
        ts = _stem(fname)
        lidar_channels.setdefault(channel, set()).add(ts)
        lidar_index[(channel, ts)] = key

    camera_channels: Dict[str, Set[str]] = {}
    camera_index: Dict[Tuple[str, str], str] = {}

    for obj in s3_service.list_all_objects(bucket, camera_prefix):
        key = obj.get("Key") or obj.get("key")
        if not key or not _is_ext(key, ".jpg", ".jpeg", ".png"):
            continue
        # 结构：camera/<channel>/<timestamp>.<ext>
        rel = key[len(camera_prefix) :].lstrip("/")
        if "/" not in rel:
            continue
        channel, fname = rel.split("/", 1)
        ts = _stem(fname)
        camera_channels.setdefault(channel, set()).add(ts)
        camera_index[(channel, ts)] = key

    # check camera_channels and calibration
    _check_camera_channel_and_camera_calibration(camera_channels, calibration)

    # ego_pose：ts -> key
    ego_pose_index: Dict[str, str] = {}
    for obj in s3_service.list_all_objects(bucket, ego_pose_prefix):
        key = obj.get("Key") or obj.get("key")
        if not key or not _is_ext(key, ".json"):
            continue
        ts = _stem(key)
        if "/" in ts:
            ts = _stem(ts.split("/")[-1])
        ego_pose_index[ts] = key

    if not lidar_channels:
        raise ValueError("未在 lidar/ 目录下发现任何激光通道数据。")

    # 3) 选择 main_channel
    def pick_main_channel() -> str:
        if main_channel in lidar_channels:
            return main_channel
        else:
            raise ValueError(f"指定的主通道 {main_channel} 在 lidar/ 目录下未找到。")

    main_channel = pick_main_channel()
    baseline_ts = sorted(lidar_channels[main_channel], key=lambda x: _ns_to_int(x))

    if not baseline_ts:
        raise ValueError(f"主通道 {main_channel} 下未发现任何 .pcd 帧。")

    # 4) 构建 frames：以主通道时间戳作为帧集合
    frames: List[FrameMetadata] = []
    for idx, ts in enumerate(baseline_ts):
        # lidars: 收集同时间戳的所有激光通道（至少包含 main_channel）
        lidars: Dict[str, str] = {}
        for ch in lidar_channels.keys():
            key = lidar_index.get((ch, ts))
            if key:
                if use_presigned_urls:
                    lidars[ch] = _as_url(s3_service, project, key)
                else:
                    lidars[ch] = _as_key(s3_service, project, key)
        if main_channel not in lidars:
            # 按理不会发生（baseline 来源于 main_channel），严防一致性问题
            raise ValueError(f"时间戳 {ts} 缺少主通道 {main_channel} 的点云。")

        # images: 收集同时间戳的所有相机图片（不可空）
        images: Dict[str, str] = {}
        for ch in camera_channels.keys():
            key = camera_index.get((ch, ts))
            if key:
                images[ch] = _as_url(s3_service, project, key)
            else:
                raise ValueError(f"时间戳 {ts} 缺少相机通道 {ch} 的图片。")
        if not images:
            raise ValueError(f"时间戳 {ts} 缺少任何相机图片。")

        # ego pose：可空；若存在严格校验为 Pose
        pose: Optional[Pose] = None
        pose_key = ego_pose_index.get(ts)
        if pose_key:
            pose_raw = s3_service.read_json_object(bucket, pose_key)
            pose = Pose.model_validate(pose_raw)  # 不一致直接抛错

        prev_ts = baseline_ts[idx - 1] if idx > 0 else ""
        next_ts = baseline_ts[idx + 1] if idx < len(baseline_ts) - 1 else ""

        # annotation: 可空；若存在严格校验为 AnnotationItem 列表
        annotation: Optional[List[AnnotationItem]] = None
        label_key = _safe_join(root, "label", f"{ts}.json")
        try:
            if s3_service.object_exists(bucket, label_key):
                label_data = s3_service.read_json_object(bucket, label_key)
                if isinstance(label_data, list):
                    annotation = [
                        AnnotationItem.model_validate(item) for item in label_data
                    ]
                else:
                    raise ValueError(f"标注数据 {label_key} 格式错误，应为列表。")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                # 如果没有标注文件，则 annotation 为空
                annotation = None
            else:
                raise ValueError(f"读取标注文件 {label_key} 时发生错误：{e}")

        frames.append(
            FrameMetadata(
                id=idx,  # 连续编号
                timestamp_ns=ts,
                prev_timestamp_ns=prev_ts,
                next_timestamp_ns=next_ts,
                lidars=lidars,
                images=images or None,
                pose=pose,
                annotation=annotation,
            )
        )

    # 5) 摘要
    start_ts = baseline_ts[0]
    end_ts = baseline_ts[-1]
    duration_seconds = max(0.0, (_ns_to_int(end_ts) - _ns_to_int(start_ts)) / 1e9)

    project_meta_response = ProjectMetadataResponse(
        project=_project_to_response(project),
        frame_count=len(frames),
        start_timestamp_ns=start_ts,
        end_timestamp_ns=end_ts,
        duration_seconds=duration_seconds,
        main_channel=main_channel,
        calibration=calibration,
        frames=frames,
    )

    # 6) 组装返回
    return project_meta_response
