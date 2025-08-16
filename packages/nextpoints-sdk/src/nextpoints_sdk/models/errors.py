from pydantic import BaseModel
from typing import Optional, Dict, Any
from .enums import ErrorCode


class ErrorModel(BaseModel):
    code: ErrorCode
    message: str
    detail: Optional[Dict[str, Any]] = None
