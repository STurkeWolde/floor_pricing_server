import csv
from fastapi import APIRouter, UploadFile, Depends
from sqlalchemy.orm import Session

from app.backend import database
from app.backend import models

router = APIRouter(prefix="/qfloors", tags=["QFloors Import/Export"])

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/import")
async def import_qfloors(file: UploadFile, db: Session = Depends(get_db)):
    contents = await file.read()
    lines = contents.decode().splitlines()
    reader = csv.DictReader(lines)

    for row in reader:
        vendor_name = row.get("Manufacturer")
        vendor = db.query(models.Vendor).filter_by(name=vendor_name).first()
        if not vendor:
            vendor = models.Vendor(name=vendor_name)
            db.add(vendor)
            db.commit()
            db.refresh(vendor)

        product = models.Product(
            sku=row["SKU"],
            style=row.get("Style Name", ""),
            color=row.get("Color Name", ""),
            product_type=row.get("Product Type", ""),
            pricing_unit=row.get("Pricing Unit", ""),
            price=float(row.get("Price", 0.0)),
            vendor_id=vendor.id
        )
        db.add(product)
    db.commit()
    return {"status": "QFloors CSV imported"}


