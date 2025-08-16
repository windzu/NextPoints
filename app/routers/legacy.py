from fastapi import APIRouter, HTTPException
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List
import numpy as np
from typing import List, Optional, Any, Union
from sqlmodel import SQLModel, create_engine, Session, select
from fastapi import APIRouter, Depends, HTTPException, Query
import logging

from nextpoints_sdk.models.annotation import AnnotationItem
from nextpoints_sdk.models.project import Project

from algos import pre_annotate
from app.models.legacy_model import PointCloudRequest, FrameRequest
from app.services.s3_service import S3Service
from app.database import get_session

router = APIRouter()

# 兼容现有 CherryPy 接口
logger = logging.getLogger(__name__)


@router.get("/")
async def read_root():
    return {"message": "Welcome to the legacy API"}


@router.post("/predict_rotation")
async def predict_rotation(data: PointCloudRequest):
    try:
        # 检查维度是否符合 Nx3
        points_array = np.array(data.points)

        if points_array.ndim != 2 or points_array.shape[1] != 3:
            raise HTTPException(
                status_code=400, detail="Input must be Nx3 point cloud data."
            )

        angle = pre_annotate.predict_yaw(points_array)

        return {"angle": angle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/auto_annotate")
async def auto_annotate():
    # 这里实现自动标注的逻辑
    return {"status": "success", "annotations": []}


@router.get("/load_annotation", response_model=List[AnnotationItem])
async def load_annotation(
    scene: str,
    frame: str,
    session: Session = Depends(get_session),
):
    """
    加载指定 scene + frame 的标注数据。
    返回 JSON,前端 xhr.responseText 仍是字符串，能被 anno_to_boxes() 使用。
    """
    try:
        # 1. check scene 和 frame 是否有效
        project_name = scene
        project: Optional[Project] = session.exec(
            select(Project).where(Project.name == project_name)
        ).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project not found: {project_name}"
            )

        # 2. instantiate S3Service
        s3_service = S3Service(
            access_key_id=project.access_key_id,
            secret_access_key=project.secret_access_key,
            endpoint_url=project.s3_endpoint,
            region_name=project.region_name,
        )

        # 3. load annotation data
        annotation_key = f"{project_name}/nextpoints/label/{frame}.json"
        # check if annotation_key exists
        try:
            if not s3_service.object_exists(project.bucket_name, annotation_key):
                return []
            # read JSON object from S3
            annotation_data = s3_service.read_json_object(
                project.bucket_name, annotation_key
            )
            if not annotation_data:
                return []
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Annotation not found: {annotation_key}, Error: {str(e)}",
            )
        # 4. convert to AnnotationItem list
        annotations = [AnnotationItem(**item) for item in annotation_data]
        return annotations
    except Exception as e:
        logger.exception("Unexpected error in load_annotation")
        raise
        raise HTTPException(
            status_code=500, detail=f"Failed to load annotation: {str(e)}"
        )


@router.get("/datameta")
async def get_data_meta():
    # 这里实现获取所有场景元数据的逻辑
    return {"status": "success", "metadata": []}


@router.get("/scenemeta")
async def get_scene_meta(scene_id: int):
    # 这里实现获取单个场景元数据的逻辑
    return {"status": "success", "scene_id": scene_id, "metadata": {}}


@router.post("/run_model")
async def run_model(data: dict):
    # 这里实现远程模型推理的逻辑
    return {"status": "success", "result": data}
