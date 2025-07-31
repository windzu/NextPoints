from typing import List, Dict, Any
from sqlmodel import Session
from models import Project, Task

def load_scene_data(scene_id: int, db: Session) -> Dict[str, Any]:
    # Load scene data from the database based on the scene_id
    scene = db.query(Project).filter(Project.id == scene_id).first()
    if scene:
        return {
            "id": scene.id,
            "name": scene.name,
            "description": scene.description,
            "s3_source_path": scene.s3_source_path,
            "tasks": [task.id for task in scene.tasks]
        }
    return {}

def save_scene_data(scene_data: Dict[str, Any], db: Session) -> Project:
    # Save or update scene data in the database
    scene = Project(**scene_data)
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene

def get_all_scenes(db: Session) -> List[Dict[str, Any]]:
    # Retrieve all scenes from the database
    scenes = db.query(Project).all()
    return [{"id": scene.id, "name": scene.name} for scene in scenes]