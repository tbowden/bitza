"""Utility schemas"""

from pydantic import BaseModel, Field
from typing import Optional

class SuccessMessageResponse(BaseModel):
    detail: Optional[str] = Field(
            None, description="Description of successful operation"
        )
    code: Optional[str] = Field(
            None, description="20x success code"
        )

class ErrorMessageResponse(BaseModel):
    detail: Optional[str] = Field(
            None, description="Description of failed operation"
        )
    code: Optional[str] = Field(
            None, description="Application specific failure code"
        )

    

