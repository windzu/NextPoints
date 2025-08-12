from sqlmodel import Session
from fastapi import APIRouter, HTTPException, Depends, status
from collections import defaultdict
import posixpath
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List,Set,Tuple
from botocore.exceptions import ClientError
from sqlmodel import select


from app.services.s3_service import S3Service
from app.models.project_model import Project,ProjectResponse,ProjectCreateRequest,ProjectStatus
from app.models.meta_data_model import FrameMetadata,CalibrationMetadata,ProjectMetadataResponse,Pose
from app.models.annotation_model import AnnotationItem,FrameAnnotation

from app.database import get_session

from tools.check_label import LabelChecker

logger = logging.getLogger(__name__)

def create_project(
    request: ProjectCreateRequest,
    session: Session = Depends(get_session)
) -> ProjectResponse:
    """
    创建新项目并从 S3 同步帧和标定数据。
    (Creates a new project and syncs frame and calibration data from S3.)
    """
    # 1. 初始化并测试 S3 连接
    # (Initialize and test S3 connection)
    s3_service = S3Service(
        access_key_id=request.access_key_id,
        secret_access_key=request.secret_access_key,
        endpoint_url=request.s3_endpoint,
        region_name=request.region_name
    )
    
    success, message = s3_service.test_connection(request.bucket_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"S3 connection failed: {message}"
        )
    
    try:
        existing = session.exec(
            select(Project).where(Project.name == request.project_name)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with name '{request.project_name}' already exists."
            )


        # 2. 创建项目记录
        # (Create the Project record)
        project = Project(
            name=request.project_name,
            description=request.description,
            storage_type=request.storage_type,
            storage_title=request.storage_title,
            bucket_name=request.bucket_name,
            bucket_prefix=request.bucket_prefix,
            region_name=request.region_name,
            s3_endpoint=request.s3_endpoint,
            access_key_id=request.access_key_id,
            secret_access_key=request.secret_access_key,
            use_presigned_urls=request.use_presigned_urls,
            expiration_minutes=request.expiration_minutes,
            status=ProjectStatus.unstarted,  # 初始状态为未开始
        )
        
        session.add(project)
        session.commit()
        session.refresh(project)

        # 3. use get_project_metadata to check project metadata
        get_project_metadata(project.name, session)

        # 4. return project response
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_at=project.created_at.isoformat(),  # 👈 转成字符串
        )
    
    except Exception as e:
        # 捕获其他所有异常（如数据库错误、S3读取错误）
        # (Catch all other exceptions, e.g., DB errors, S3 read errors)
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during project creation: {e}"
        )

def get_project_metadata(
    project_name: str,
    session: Session = Depends(get_session)
) -> ProjectMetadataResponse:
    """
    获取项目完整元数据。优先读取meta.json，若不存在则生成。
    """
    # 1. 获取项目基本信息和状态
    project = session.exec(
        select(Project).where(Project.name == project_name)
    ).first()


    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 2. 初始化S3服务
    s3_service = S3Service(
        access_key_id=project.access_key_id,
        secret_access_key=project.secret_access_key,
        endpoint_url=project.s3_endpoint,
        region_name=project.region_name
    )

    # 3. 每次获取元数据时都生成 meta.json
    # 这是为了确保数据是最新的，避免缓存问题
    try:
        # meta_content = _generate_and_upload_meta_json(project, s3_service)
        project_meta_data = _generate_project_meta_data(project, s3_service)
        return project_meta_data
    except Exception as e:
        # 捕获生成 meta.json 时的任何异常
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate_project_meta_data: {str(e)}"
        )


def get_check_label(
    project_name: str,
    session: Session = Depends(get_session)
) -> List[Dict[str, Any]]:
    """
    获取项目的标注检查数据
    """
    try:
        # 1. 获取项目基本信息和状态
        project = session.exec(
            select(Project).where(Project.name == project_name)
        ).first()

        # 2. build FrameAnnotation list from label files
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        s3_service = S3Service(
            access_key_id=project.access_key_id,
            secret_access_key=project.secret_access_key,
            endpoint_url=project.s3_endpoint,
            region_name=project.region_name
        )
        label_key_prefix = str(Path(project.bucket_prefix or "") / "label")
        label_files = s3_service.list_objects(project.bucket_name, label_key_prefix)
        if not label_files:
            raise HTTPException(status_code=404, detail="No label files found for this project")
        annotations = []
        for label_file in label_files:
            key = label_file['key']
            relative_key = key[len(label_key_prefix):].lstrip('/') if label_key_prefix else key
            frame_id = Path(relative_key).stem  # 获取帧ID
            
            try:
                annotation_data = s3_service.read_json_object(project.bucket_name, key)
                if not isinstance(annotation_data, list):
                    annotation_data = []  # 确保是列表格式
                annotations.append(FrameAnnotation(
                    scene=project.name,
                    frame=frame_id,
                    annotation=[AnnotationItem(**item) for item in annotation_data]
                ))
            except Exception as e:
                logger.error(f"Failed to read or parse label file {key}: {e}")
                continue

        # 3. use LabelChecker to validate annotations
        label_checker = LabelChecker(annotations)
        label_checker.check()
        return label_checker.messages

    except Exception as e:
        logger.error(f"Failed to get label check data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get label check data: {str(e)}"
        )

def save_world_list(
    request: List[FrameAnnotation],
    session: Session = Depends(get_session)
):
    """
    保存单个项目的多个世界帧的标注数据到S3存储
    """

    try:
        if not request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request data cannot be empty"
            )

        # 确保所有条目的 scene 一致
        scenes = set(item.scene for item in request)
        if len(scenes) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"All frames must belong to the same project. Found: {list(scenes)}"
            )

        project_name = request[0].scene

        # 获取项目信息
        project = session.exec(
            select(Project).where(Project.name == project_name)
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_name} not found"
            )

        # 初始化 S3 服务
        s3_service = S3Service(
            access_key_id=project.access_key_id,
            secret_access_key=project.secret_access_key,
            endpoint_url=project.s3_endpoint,
            region_name=project.region_name
        )

        saved_count = 0

        # 保存每帧
        for item in request:
            try:
                prefix = project.bucket_prefix or ""
                if prefix and not prefix.endswith("/"):
                    prefix += "/"

                label_key = f"{prefix}label/{item.frame}.json"

                s3_service.upload_json_object(
                    bucket_name=project.bucket_name,
                    key=label_key,
                    data_dict=item.to_dict()["annotation"]
                )

                saved_count += 1

            except Exception as e:
                logger.error(f"Failed to save annotation for {project_name}/{item.frame}: {e}")
                logger.error(f"Annotation data: {item.annotation}")
                continue

        return {
            "message": f"Successfully saved {saved_count} annotations",
            "saved_count": saved_count,
            "total_requested": len(request)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save world list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save annotations: {str(e)}"
        )

def _generate_project_meta_data(
    project: Project,
    s3_service: S3Service,
    main_channel: Optional[str] = "lidar-fusion"
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

    def _as_url(s3: S3Service, project: Project, bucket_key: str) -> str:
        """如需 URL，可用该函数替换 _as_key 的调用"""
        return s3.get_object_url(
            bucket_name=project.bucket_name,
            object_key=bucket_key,
            use_presigned=project.use_presigned_urls,
            expiration=project.expiration_minutes * 60,
        )


    bucket = project.bucket_name
    root = _safe_join(project.bucket_prefix or "")

    calib_prefix   = _safe_join(root, "calib")
    lidar_prefix   = _safe_join(root, "lidar")
    camera_prefix  = _safe_join(root, "camera")
    ego_pose_prefix= _safe_join(root, "ego_pose")

    # 1) 读 calib：严格校验为 CalibrationMetadata
    calibration: Dict[str, CalibrationMetadata] = {}
    for obj in s3_service.list_all_objects(bucket, calib_prefix):
        key = obj.get("Key") or obj.get("key")
        if not key or not _is_ext(key, ".json"):
            continue
        raw = s3_service.read_json_object(bucket, key)
        meta = CalibrationMetadata.model_validate(raw)  # 不一致直接抛错
        chan = meta.channel or _stem(key)  # 以 JSON 内 channel 为准，缺失则用文件名
        # 如需防止重复 channel 直接报错，可启用以下检查
        # if chan in calibration:
        #     raise ValueError(f"重复的 calibration channel: {chan}")
        calibration[chan] = meta

    # 2) 枚举 lidar/camera 子通道及各自的时间戳索引
    lidar_channels: Dict[str, Set[str]] = {}   # channel -> {timestamp_ns}
    lidar_index: Dict[Tuple[str, str], str] = {}  # (channel, ts) -> key

    for obj in s3_service.list_all_objects(bucket, lidar_prefix):
        key = obj.get("Key") or obj.get("key")
        if not key or not _is_ext(key, ".pcd"):
            continue
        # 结构：lidar/<channel>/<timestamp>.pcd
        rel = key[len(lidar_prefix):].lstrip("/")  # <channel>/<file>
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
        rel = key[len(camera_prefix):].lstrip("/")
        if "/" not in rel:
            continue
        channel, fname = rel.split("/", 1)
        ts = _stem(fname)
        camera_channels.setdefault(channel, set()).add(ts)
        camera_index[(channel, ts)] = key

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
        if len(lidar_channels) == 1:
            return next(iter(lidar_channels.keys()))
        return sorted(lidar_channels.keys())[0]

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
                lidars[ch] = _as_url(s3_service, project, key)
        if main_channel not in lidars:
            # 按理不会发生（baseline 来源于 main_channel），严防一致性问题
            raise ValueError(f"时间戳 {ts} 缺少主通道 {main_channel} 的点云。")

        # images: 收集同时间戳的所有相机图片（可空）
        images: Dict[str, str] = {}
        for ch in camera_channels.keys():
            key = camera_index.get((ch, ts))
            if key:
                images[ch] = _as_url(s3_service, project, key)

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
            label_data = s3_service.read_json_object(bucket, label_key)
            if isinstance(label_data, list):
                annotation = [AnnotationItem.model_validate(item) for item in label_data]
            else:
                raise ValueError(f"标注数据 {label_key} 格式错误，应为列表。")
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # 如果没有找到标注文件，则 annotation 为空
                annotation = None
            else:
                raise ValueError(f"读取标注文件 {label_key} 失败: {e}")

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
