from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from app.models import Project
from app.database import get_session
from app.models import ProjectResponse, ProjectCreateRequest, ProjectStatusUpdateRequest
from app.models import ProjectStatus,Frame
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
            for frame_data in frames_data:
                frame = Frame(
                    project_id=project.id,
                    timestamp_ns=frame_data['timestamp_ns'],
                    pointcloud_s3_key=frame_data['pointcloud_s3_key'],
                    images=frame_data['images'] if frame_data['images'] else None
                )
                session.add(frame)
            
            session.commit()
            
            logger.info(f"Created project '{project.name}' with {len(frames_data)} frames")
            
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

    return {
        "project_id": project.id,
        "frame": frame,
        "ego_pose": frame_data.pose
    }