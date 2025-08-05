from sqlmodel import Session
from fastapi import APIRouter, HTTPException, Depends, status
from collections import defaultdict
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
from sqlmodel import select


from app.services.s3_service import S3Service
from app.models.project_model import Project,ProjectResponse,ProjectCreateRequest,ProjectStatus
from app.models.meta_data_model import FrameMetadata,CalibrationMetadata,ProjectMetadataResponse
from app.models.annotation_model import AnnotationItem,WorldAnnotation

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
            s3_root_path=f"s3://{request.bucket_name}/{request.bucket_prefix or ''}",
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

        # 3. check meta.json 是否存在
        # (Check if meta.json exists)
        meta_key = str(Path(project.bucket_prefix or "") / "meta.json")
        try:
            meta_content = s3_service.read_json_object(project.bucket_name, meta_key)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # 如果不存在，生成并上传 meta.json
                # (If not exists, generate and upload meta.json)
                meta_content = _generate_and_upload_meta_json(project, s3_service)
            else:
                # 处理其他可能的 S3 错误（如权限问题）
                raise HTTPException(status_code=500, detail=f"S3 error reading meta.json: {e}")



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

    # 3. 尝试读取 meta.json，如果失败则生成它
    meta_key = str(Path(project.bucket_prefix or "") / "meta.json")
    try:
        meta_content = s3_service.read_json_object(project.bucket_name, meta_key)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            meta_content = _generate_and_upload_meta_json(project, s3_service)
        else:
            # Handle other potential S3 errors (e.g., permissions)
            raise HTTPException(status_code=500, detail=f"S3 error reading meta.json: {e}")

    # --- 从这里开始，我们保证已经拿到了 meta_content ---
    # 4. 转换元数据：用预签名URL替换S3 Keys
    frames_metadata_list = []
    for frame_data in meta_content.get("frames", []):
        # 为点云生成预签名URL
        pointcloud_url = s3_service.generate_presigned_url(
            project.bucket_name, frame_data["pointcloud_key"], project.expiration_minutes
        )

        # 为所有图像生成预签名URL
        image_urls = {}
        if "image_keys" in frame_data:
            for cam_id, image_key in frame_data["image_keys"].items():
                url = s3_service.generate_presigned_url(
                    project.bucket_name, image_key, project.expiration_minutes
                )
                if url:
                    image_urls[cam_id] = url
        
        # 处理annotation数据，确保格式正确
        annotation_data = frame_data.get("annotation", [])
        if not isinstance(annotation_data, list):
            annotation_data = []
        
        # 验证annotation数据格式
        validated_annotations = []
        for ann in annotation_data:
            try:
                validated_annotations.append(AnnotationItem(**ann))
            except Exception as e:
                print(f"Warning: Invalid annotation item in frame {frame_data['timestamp_ns']}: {e}")
                continue
        
        frames_metadata_list.append(
            FrameMetadata(
                # 注意：Frame ID 现在不存在于 meta.json 中，这是一个设计选择。
                # 如果需要，生成脚本也可以从文件名或其他地方推断一个唯一标识符。
                # 这里我们用时间戳的哈希值或索引作为临时ID，或设为0。
                id=hash(frame_data["timestamp_ns"]),
                timestamp_ns=frame_data["timestamp_ns"],
                prev_timestamp_ns=frame_data.get("prev_timestamp_ns"),
                next_timestamp_ns=frame_data.get("next_timestamp_ns"),
                pointcloud_url=pointcloud_url or "",
                images=image_urls,
                pose=frame_data.get("pose"),
                annotation=validated_annotations,
                # annotation_status 不再由帧管理
            )
        )

    # 5. 组装并返回最终的响应对象
    # 项目状态从数据库获取，元数据从JSON文件获取
    project_response = ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at.isoformat(),  # 转成字符串
    )
    summary = meta_content.get("summary", {})
    
    return ProjectMetadataResponse(
        project=project_response,
        frame_count=summary.get("frame_count", 0),
        start_timestamp_ns=summary.get("start_timestamp_ns"),
        end_timestamp_ns=summary.get("end_timestamp_ns"),
        duration_seconds=summary.get("duration_seconds", 0.0),
        calibration={
            sensor_id: CalibrationMetadata(**calib_dict)
            for sensor_id, calib_dict in meta_content.get("calibration", {}).items()
        },
        frames=frames_metadata_list
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

        # 2. build WorldAnnotation list from label files
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
                annotations.append(WorldAnnotation(
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
    request: List[WorldAnnotation],
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

def _generate_and_upload_meta_json(
    project: Project, 
    s3_service: S3Service
) -> Dict[str, Any]:
    """
    通过扫描S3生成meta.json文件,上传它,并返回其内容。
    这是一个耗时操作，只应在首次访问项目时调用一次。
    """
    print(f"Meta.json not found for project {project.id}. Generating now...")
    prefix = project.bucket_prefix or ""
    all_objects = s3_service.list_objects(project.bucket_name, prefix)

    # --- Step 1: Parse all S3 files (similar to original sync logic) ---
    frames_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"image_keys": {}, "annotation": []})
    calib_files = {}

    for obj in all_objects:
        key = obj['key']
        relative_key = key[len(prefix):].lstrip('/') if prefix else key
        path_parts = Path(relative_key).parts
        
        if not path_parts or path_parts[-1] == "meta.json":
            continue

        try:
            if path_parts[0] == 'lidar':
                timestamp = Path(path_parts[-1]).stem
                frames_data[timestamp]['pointcloud_key'] = key
            elif path_parts[0] == 'camera':
                timestamp = Path(path_parts[-1]).stem
                cam_id = path_parts[1]
                frames_data[timestamp]['image_keys'][cam_id] = key
            elif path_parts[0] == 'ego_pose':
                timestamp = Path(path_parts[-1]).stem
                # Directly read and embed pose data
                pose_content = s3_service.read_json_object(project.bucket_name, key)
                frames_data[timestamp]['pose'] = pose_content
            elif path_parts[0] == 'label':
                timestamp = Path(path_parts[-1]).stem
                # Directly read and embed annotation data
                try:
                    annotation_content = s3_service.read_json_object(project.bucket_name, key)
                    # 确保annotation是列表格式，如果为空则设为空列表
                    if annotation_content is None:
                        annotation_content = []
                    elif not isinstance(annotation_content, list):
                        print(f"Warning: Annotation file {key} is not a list, setting to empty list")
                        annotation_content = []
                    frames_data[timestamp]['annotation'] = annotation_content
                except Exception as e:
                    print(f"Warning: Could not read annotation file {key}: {e}")
                    frames_data[timestamp]['annotation'] = []
            elif path_parts[0] == 'calib':
                sensor_id = Path(path_parts[-1]).stem
                calib_content = s3_service.read_json_object(project.bucket_name, key)
                calib_files[sensor_id] = calib_content
        except Exception as e:
            print(f"Warning: Skipping file {key} due to parsing error: {e}")
            continue
            
    # --- Step 2: Assemble and Sort Frames ---
    sorted_timestamps = sorted(frames_data.keys())
    frames_list = []
    for ts in sorted_timestamps:
        if 'pointcloud_key' in frames_data[ts]:
            frames_list.append({
                "timestamp_ns": ts,
                **frames_data[ts]
            })

    # --- Step 3: Add prev/next links ---
    for i, frame in enumerate(frames_list):
        frame["prev_timestamp_ns"] = frames_list[i-1]["timestamp_ns"] if i > 0 else None
        frame["next_timestamp_ns"] = frames_list[i+1]["timestamp_ns"] if i < len(frames_list) - 1 else None
        
    # --- Step 4: Calculate Summary ---
    frame_count = len(frames_list)
    start_ts, end_ts, duration_sec = None, None, 0.0
    if frame_count > 0:
        start_ts = frames_list[0]["timestamp_ns"]
        end_ts = frames_list[-1]["timestamp_ns"]
        if frame_count > 1:
            duration_sec = (int(end_ts) - int(start_ts)) / 1_000_000_000.0
            
    # --- Step 5: Assemble Final meta.json Content ---
    meta_content = {
        "meta_version": "1.0",
        "summary": {
            "project_name": project.name,
            "description": project.description,
            "frame_count": frame_count,
            "start_timestamp_ns": start_ts,
            "end_timestamp_ns": end_ts,
            "duration_seconds": round(duration_sec, 3),
            "sensors_present": list(calib_files.keys())
        },
        "calibration": calib_files,
        "frames": frames_list
    }

    # --- Step 6: Upload to S3 ---
    meta_key = str(Path(prefix) / "meta.json")
    s3_service.upload_json_object(project.bucket_name, meta_key, meta_content)
    print(f"Successfully generated and uploaded meta.json to s3://{project.bucket_name}/{meta_key}")
    
    return meta_content