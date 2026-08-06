from pydantic import BaseModel, ConfigDict

from app.models.enums import VendorType


class VendorCreate(BaseModel):
    name: str
    vendor_type: VendorType = VendorType.SUBCONTRACTOR
    trade: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    phone: str | None = None


class VendorOut(VendorCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
