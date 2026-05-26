# app/api/schemas.py
from pydantic import BaseModel

class InquiryRequest(BaseModel):
    """Modelo de entrada para envio de uma nova dúvida do cliente."""
    inquiry: str

class FeedbackRequest(BaseModel):
    """Modelo de entrada para envio de feedback humano no fluxo de HITL."""
    feedback: str
