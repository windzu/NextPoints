from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from app.models import Project, Frame, Calibration, Annotation
from app.database import get_session
from app.models import (
    ProjectResponse, ProjectCreateRequest, ProjectStatusUpdateRequest,
    ProjectStatus, FrameMetadata, CalibrationMetadata, ProjectMetadataResponse
)
from app.services.s3_service import S3Service
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreateRequest,
    session: Session = Depends(get_session)
):
    """
    创建新项目并同步 S3 数据
    """
    try:
        # 1. 测试 S3 连接
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
        
        # 2. 创建项目记录
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
            status=ProjectStatus.unstarted
        )
        
        session.add(project)
        session.commit()
        session.refresh(project)
        
        # 3. 同步 S3 数据
        try:
            frames_data = s3_service.sync_project_data(
                request.bucket_name, 
                request.bucket_prefix or ""
            )
            
            # 4. 创建帧记录
            all_camera_ids = set()
            for frame_data in frames_data:
                frame = Frame(
                    project_id=project.id,
                    timestamp_ns=frame_data['timestamp_ns'],
                    pointcloud_s3_key=frame_data['pointcloud_s3_key'],
                    images=frame_data['images'] if frame_data['images'] else None
                )
                session.add(frame)
                
                # 收集所有相机ID
                if frame_data.get('images'):
                    all_camera_ids.update(frame_data['images'].keys())
            
            # 5. 创建默认标定信息
            if all_camera_ids:
                # 为每个检测到的相机创建默认内参
                default_intrinsics = {}
                default_extrinsics = {}
                
                for camera_id in all_camera_ids:
                    # 创建默认内参 (示例值，实际应用中需要真实标定数据)
                    default_intrinsics[camera_id] = {
                        "fx": 800.0,
                        "fy": 800.0, 
                        "cx": 320.0,
                        "cy": 240.0,
                        "k1": 0.0,
                        "k2": 0.0,
                        "p1": 0.0,
                        "p2": 0.0
                    }
                    
                    # 创建默认外参 (相机到激光雷达的变换，示例值)
                    default_extrinsics[camera_id] = {
                        "translation": [0.0, 0.0, 0.0],
                        "rotation": [1.0, 0.0, 0.0, 0.0]  # 四元数 [w, x, y, z]
                    }
                
                # 创建标定记录
                calibration = Calibration(
                    project_id=project.id,
                    intrinsics=default_intrinsics,
                    extrinsics=default_extrinsics
                )
                session.add(calibration)
            
            session.commit()
            
            logger.info(f"Created project '{project.name}' with {len(frames_data)} frames and {len(all_camera_ids)} cameras")
            
        except Exception as e:
            # 如果同步失败，删除已创建的项目
            session.delete(project)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to sync S3 data: {str(e)}"
            )
        
        project_response = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_at=project.created_at.isoformat(),
            frame_count=len(frames_data)
        )

        return project_response
        
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/list_projects", response_model=List[ProjectResponse])
async def list_projects(
    status_filter: Optional[ProjectStatus] = None,
    session: Session = Depends(get_session)
):
    """
    获取项目列表，支持按状态过滤
    """
    try:
        query = select(Project)
        if status_filter:
            query = query.where(Project.status == status_filter)
        
        projects = session.exec(query).all()
        
        result = []
        for project in projects:
            # 计算帧数量
            frame_count = len(project.frames)
            
            result.append(ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                status=project.status,
                created_at=project.created_at.isoformat(),
                frame_count=frame_count
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    session: Session = Depends(get_session)
):
    """
    获取单个项目详情
    """
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at.isoformat(),
        frame_count=len(project.frames)
    )


@router.get("/{project_id}/metadata", response_model=ProjectMetadataResponse)
async def get_project_metadata(
    project_id: int,
    session: Session = Depends(get_session)
):
    """
    获取项目完整元数据，包括所有帧信息和预签名URL
    """
    try:
        # 1. 获取项目信息
        project = session.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 2. 初始化S3服务
        s3_service = S3Service(
            access_key_id=project.access_key_id,
            secret_access_key=project.secret_access_key,
            endpoint_url=project.s3_endpoint,
            region_name=project.region_name
        )
        
        # 3. 获取所有帧数据
        frames_query = select(Frame).where(Frame.project_id == project_id).order_by(Frame.timestamp_ns)
        frames = session.exec(frames_query).all()
        
        # 4. 收集所有需要生成预签名URL的文件
        all_s3_keys = []
        for frame in frames:
            # 点云文件
            if frame.pointcloud_s3_key:
                all_s3_keys.append(frame.pointcloud_s3_key)
            
            # 图像文件
            if frame.images:
                for camera_id, image_key in frame.images.items():
                    if image_key:
                        all_s3_keys.append(image_key)
        
        # 5. 批量生成预签名URL
        expiration_seconds = project.expiration_minutes * 60
        presigned_urls = s3_service.get_batch_presigned_urls(
            project.bucket_name, 
            all_s3_keys, 
            expiration_seconds
        )
        
        # 6. 构建帧元数据响应
        frame_metadata_list = []
        for frame in frames:
            # 获取点云预签名URL
            pointcloud_url = presigned_urls.get(frame.pointcloud_s3_key, "")
            
            # 获取图像预签名URL
            image_urls = {}
            if frame.images:
                for camera_id, image_key in frame.images.items():
                    if image_key and image_key in presigned_urls:
                        image_urls[camera_id] = presigned_urls[image_key]
            
            frame_metadata = FrameMetadata(
                id=frame.id or 0,  # 确保id不为None
                timestamp_ns=frame.timestamp_ns,
                pointcloud_url=pointcloud_url,
                images=image_urls if image_urls else None,
                pose=frame.pose,
                annotation_status=frame.annotation_status
            )
            frame_metadata_list.append(frame_metadata)
        
        # 7. 获取标定信息
        calibration_query = select(Calibration).where(Calibration.project_id == project_id)
        calibration = session.exec(calibration_query).first()
        
        calibration_metadata = CalibrationMetadata(
            intrinsics=calibration.intrinsics if calibration else {},
            extrinsics=calibration.extrinsics if calibration else {}
        )
        
        # 8. 构建项目响应
        project_response = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_at=project.created_at.isoformat(),
            frame_count=len(frames)
        )
        
        # 9. 返回完整元数据
        return ProjectMetadataResponse(
            project=project_response,
            frames=frame_metadata_list,
            calibration=calibration_metadata
        )
        
    except Exception as e:
        logger.error(f"Failed to get project metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project metadata: {str(e)}"
        )


@router.put("/{project_id}/status", response_model=ProjectResponse)
async def update_project_status(
    project_id: int,
    request: ProjectStatusUpdateRequest,
    session: Session = Depends(get_session)
):
    """
    更新项目状态
    """
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    project.status = request.status
    session.add(project)
    session.commit()
    session.refresh(project)
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at.isoformat(),
        frame_count=len(project.frames)
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    session: Session = Depends(get_session)
):
    """
    删除项目及其所有相关数据
    """
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # 删除项目（级联删除会自动删除相关的帧和标注数据）
    session.delete(project)
    session.commit()
    
    return {"message": f"Project {project_id} deleted successfully"}


@router.get("/{project_id}/frames")
async def get_project_frames(
    project_id: int,
    session: Session = Depends(get_session)
):
    """
    获取项目的所有帧数据
    """
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # 按时间戳排序返回帧数据
    frames = sorted(project.frames, key=lambda f: f.timestamp_ns)
    
    result = []
    for frame in frames:
        frame_data = {
            "id": frame.id,
            "timestamp_ns": frame.timestamp_ns,
            "pointcloud_s3_key": frame.pointcloud_s3_key,
            "images": frame.images or {},
            "pose": frame.pose,
            "annotation_status": frame.annotation_status
        }
        
        # 如果项目配置了预签名URL，生成访问URL
        if project.use_presigned_urls:
            s3_service = S3Service(
                access_key_id=project.access_key_id,
                secret_access_key=project.secret_access_key,
                endpoint_url=project.s3_endpoint,
                region_name=project.region_name
            )
            
            # 生成点云文件的预签名URL
            frame_data["pointcloud_url"] = s3_service.get_object_url(
                project.bucket_name,
                frame.pointcloud_s3_key,
                use_presigned=True,
                expiration=project.expiration_minutes * 60
            )
            
            # 生成图像文件的预签名URL
            if frame.images:
                frame_data["image_urls"] = {}
                for camera_id, image_key in frame.images.items():
                    frame_data["image_urls"][camera_id] = s3_service.get_object_url(
                        project.bucket_name,
                        image_key,
                        use_presigned=True,
                        expiration=project.expiration_minutes * 60
                    )
        else:
            # 构建直接访问URL
            base_url = project.s3_endpoint or f"https://{project.bucket_name}.s3.{project.region_name}.amazonaws.com"
            frame_data["pointcloud_url"] = f"{base_url}/{frame.pointcloud_s3_key}"
            
            if frame.images:
                frame_data["image_urls"] = {}
                for camera_id, image_key in frame.images.items():
                    frame_data["image_urls"][camera_id] = f"{base_url}/{image_key}"
        
        result.append(frame_data)
    
    return result

@router.get("/get_ego_pose")
async def get_ego_pose(
    scene: int,
    frame: int,
    session: Session = Depends(get_session)
):
    """
    获取项目的自我姿态数据
    """
    project_id= scene  # scene 等价于 project_id

    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # 查询对应帧的自我姿态数据
    frame_data = session.exec(
        select(Frame).where(
            Frame.project_id == project_id,
            Frame.timestamp_ns == frame
        )
    ).first()
    
    if not frame_data or not frame_data.pose:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ego pose data not found for this frame"
        )
    
    return frame_data.pose



