from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from app.models import Project
from app.database import get_session
from app.models import (
    ProjectResponse, ProjectCreateRequest, ProjectStatusUpdateRequest,
    ProjectStatus, FrameMetadata, CalibrationMetadata, ProjectMetadataResponse
)
from app.services.s3_service import S3Service
from app.services import project_service 
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
        project_response=project_service.create_project(request=request, session=session)
            
        if not project_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create project"
            )

        return project_response

    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
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
    project_name: str,
    session: Session = Depends(get_session)
):
    """
    获取项目完整元数据,包括所有帧信息和预签名URL
    """
    try:
        project_metadata = project_service.get_project_metadata(project_name, session)
        if not project_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project metadata not found"
            )
        return project_metadata
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





