from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class PointCloudRequest(BaseModel):
    points: List[List[float]]  # N x 3 数组，每个点是 [x, y, z]