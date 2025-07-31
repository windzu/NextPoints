from fastapi import APIRouter, HTTPException

router = APIRouter()

# 兼容现有 CherryPy 接口

@router.get("/")
async def read_root():
    return {"message": "Welcome to the legacy API"}

@router.post("/saveworldlist")
async def save_world_list(data: dict):
    # 这里实现保存标注数据的逻辑
    return {"status": "success", "data": data}

@router.post("/predict_rotation")
async def predict_rotation(data: dict):
    # 这里实现预测旋转角度的逻辑
    return {"status": "success", "predicted_rotation": data}

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