from pydantic import BaseModel
from typing import Optional

class PermissionCreate(BaseModel):
    name: str

class PermissionOut(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class AssignPermissions(BaseModel):
    role_id: Optional[int] = None
    user_id: Optional[int] = None
    permission_ids: list[int]
