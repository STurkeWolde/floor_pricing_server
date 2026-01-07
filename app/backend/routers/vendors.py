# app/backend/routers/vendors.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.backend import database, models, schemas

router = APIRouter(prefix="/vendors", tags=["Vendors"])

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.Vendor)
def create_vendor(vendor: schemas.VendorCreate, db: Session = Depends(get_db)):
    db_vendor = models.Vendor(**vendor.dict())
    db.add(db_vendor)
    try:
        db.commit()
    except:
        db.rollback()
        raise HTTPException(status_code=400, detail="Vendor with this name already exists")
    db.refresh(db_vendor)
    return db_vendor

@router.get("/", response_model=list[schemas.Vendor])
def list_vendors(db: Session = Depends(get_db)):
    return db.query(models.Vendor).all()

@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    db.delete(vendor)
    db.commit()
    return {"detail": "Vendor deleted successfully"}

@router.delete("/clear-all")
def clear_all_vendors(db: Session = Depends(get_db)):
    db.query(models.Vendor).delete()
    db.commit()
    return {"message": "All vendors deleted successfully"}
