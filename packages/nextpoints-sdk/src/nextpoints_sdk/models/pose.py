from pydantic import BaseModel


class Translation(BaseModel):
    x: float
    y: float
    z: float


class Rotation(BaseModel):
    x: float
    y: float
    z: float
    w: float


class Transform(BaseModel):
    translation: Translation
    rotation: Rotation


class Pose(BaseModel):
    parent_frame_id: str
    child_frame_id: str
    transform: Transform
