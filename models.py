from pydantic import BaseModel
from typing import Optional, List


class UserLogin(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    name: str
    username: str
    email: Optional[str] = None
    password: str
    role: str  # admin | manager | viewer


class UserUpdate(BaseModel):
    name: str
    username: str
    email: Optional[str] = None
    password: Optional[str] = None
    role: str


class TokenResponse(BaseModel):
    token: str
    user: dict


class LineItem(BaseModel):
    desc: str
    qty: float
    price: float


class InvoiceCreate(BaseModel):
    language: str = "en"
    status: str = "draft"
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[str] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    client_address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    notes: Optional[str] = None
    items: List[LineItem] = []


class InvoiceUpdate(InvoiceCreate):
    pass


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str = "other"
    date: Optional[str] = None
    notes: Optional[str] = None


class ExpenseUpdate(ExpenseCreate):
    pass
