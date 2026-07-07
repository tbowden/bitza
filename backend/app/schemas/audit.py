from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    action: str
    user_id: Optional[str]
    user_display_name: str = ""   # populated by service
    description: Optional[str]
    created_at: datetime
