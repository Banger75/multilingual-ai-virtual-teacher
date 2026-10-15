from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)

    class_name: str = "5"
    subject: str = ""
    book: str = ""
    language: str = "auto"

    response_mode: Literal[
        "text", "spoken", "both"
    ] = "both"