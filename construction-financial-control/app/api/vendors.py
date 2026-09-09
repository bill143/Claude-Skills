from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorOut
from app.services import audit_service

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.post("", response_model=VendorOut, status_code=201)
def create_vendor(
    body: VendorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.FINANCE)),
):
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.flush()
    audit_service.record(
        db, actor=user, entity_type="VENDOR", entity_id=vendor.id,
        action="created", payload={"name": vendor.name, "type": vendor.vendor_type.value},
    )
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("", response_model=list[VendorOut])
def list_vendors(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.execute(select(Vendor).order_by(Vendor.name)).scalars().all()


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor
