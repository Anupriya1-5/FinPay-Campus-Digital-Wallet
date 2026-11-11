from pydantic import BaseModel, Field
from typing import Optional

class LoginIn(BaseModel):
    email: str
    password: str

class RegisterStudent(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8)

class TopupIn(BaseModel):
    amount_rupees: int = Field(gt=0, le=20000)

class PaymentIn(BaseModel):
    merchant_id: int
    amount_rupees: int = Field(gt=0, le=50000)

class MerchantRegister(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8)
    shop_name: str
    category: str
    description: str = ""

class RefundIn(BaseModel):
    transaction_id: int
    reason: str = Field(min_length=5, max_length=500)

class ComplaintIn(BaseModel):
    transaction_id: Optional[int] = None
    subject: str
    description: str

class ReviewIn(BaseModel):
    decision: str
    note: str = ""
