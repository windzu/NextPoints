from fastapi import APIRouter, HTTPException
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List
import numpy as np

from algos import pre_annotate
from app.models.legacy_model import PointCloudRequest

router = APIRouter()

# 兼容现有 CherryPy 接口

@router.get("/")
async def read_root():
    return {"message": "Welcome to the legacy API"}

@router.post("/predict_rotation")
async def predict_rotation(data: PointCloudRequest):
    try:
        # 检查维度是否符合 Nx3
        points_array = np.array(data.points)

        if points_array.ndim != 2 or points_array.shape[1] != 3:
            raise HTTPException(status_code=400, detail="Input must be Nx3 point cloud data.")

        angle = pre_annotate.predict_yaw(points_array)

        return {"angle": angle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.get("/auto_annotate")
async def auto_annotate():
    # 这里实现自动标注的逻辑
    return {"status": "success", "annotations": []}

@router.get("/load_annotation")
async def load_annotation(task_id: int):
    # 这里实现加载标注数据的逻辑
    return {"status": "success", "task_id": task_id, "annotations": {}}

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