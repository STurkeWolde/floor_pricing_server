# app/backend/routers/b2b_import_export.py
import csv
import io
import logging
from typing import List

from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.backend import database, models

router = APIRouter(prefix="/b2b", tags=["B2B Import/Export"])

# logger
logger = logging.getLogger("b2b_import_export")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------
# Helpers
# ----------------------------

def normalize_unit(u: str) -> str:
    if not u:
        return "EA"
    s = str(u).strip().lower().replace(".", "").replace(" ", "")
    synonyms = {
        "sf": "SF", "sqft": "SF", "sft": "SF",
        "sy": "SY", "sqyd": "SY",
        "lf": "LF",
        "ea": "EA", "each": "EA", "pcs": "EA", "pc": "EA",
        "ct": "CT", "carton": "CT",
    }
    return synonyms.get(s, "EA")


def normalize_key(s: str) -> str:
    return str(s).strip().lower().replace("_", " ").replace("-", " ")


def get_any(row: dict, keys: list[str]):
    for k in keys:
        nk = normalize_key(k)
        for rk, rv in row.items():
            if normalize_key(rk) == nk and rv not in (None, ""):
                return rv
    return None


def find_header_row(lines: list[str]) -> int:
    REQUIRED = {"description", "ikey", "price", "color"}
    for i, line in enumerate(lines[:50]):
        cols = [c.strip().lower() for c in line.split(",")]
        if len(REQUIRED.intersection(cols)) >= 2:
            return i
    return 0


def build_reader(contents: bytes) -> csv.DictReader:
    lines = contents.decode(errors="ignore").splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="Empty CSV file")

    header_index = find_header_row(lines)
    real_lines = lines[header_index:]

    reader = csv.DictReader(real_lines)
    logger.info("Detected CSV columns: %s", reader.fieldnames)
    return reader


def resolve_product_type(row: dict, type_map: dict) -> str:
    product_group = get_any(row, ["product group", "group", "category"])
    material_type = get_any(row, ["material type", "material", "surface"])
    product_type_raw = get_any(row, ["product type", "type"])

    candidates = []
    if product_group and material_type:
        candidates.append(f"{product_group} {material_type}")
        candidates.append(f"{material_type} {product_group}")

    candidates.extend([product_group, material_type, product_type_raw])

    for v in row.values():
        if isinstance(v, str) and len(v) < 40:
            candidates.append(v)

    for c in candidates:
        if not c:
            continue
        key = normalize_key(c)
        if key in type_map:
            return type_map[key]

    return "VIN"


# ----------------------------
# Import CSV into DB
# ----------------------------

@router.post("/import/csv")
async def import_b2b_csv(file: UploadFile, db: Session = Depends(get_db)):
    contents = await file.read()
    reader = build_reader(contents)

    count = 0
    for row in reader:
        vendor_name = (
            get_any(row, ["vendor name", "manufacturer"])
            or row.get("DEALER")
            or row.get("SUPPLIER")
            or "Unknown Vendor"
        )

        vendor = db.query(models.Vendor).filter_by(name=vendor_name).first()
        if not vendor:
            vendor = models.Vendor(name=vendor_name)
            db.add(vendor)
            db.commit()
            db.refresh(vendor)

        price_raw = get_any(row, ["price", "cut cost", "base price"]) or 0
        try:
            price_f = float(str(price_raw).replace("$", "").replace(",", ""))
        except Exception:
            price_f = 0.0

        product = models.Product(
            sku=get_any(row, ["sku", "ikey"]) or "",
            style=get_any(row, ["description", "style", "pattern"]) or "",
            color=get_any(row, ["color", "colour"]) or "",
            product_type=get_any(row, ["product type"]) or "",
            pricing_unit=normalize_unit(get_any(row, ["pc", "unit", "uom", "bu"]) or ""),
            price=price_f,
            vendor_id=vendor.id,
        )

        db.add(product)
        count += 1

    db.commit()
    return {"status": "✅ B2B CSV imported successfully", "imported": count}


# ----------------------------
# Preview conversion
# ----------------------------

@router.post("/preview", response_class=JSONResponse)
async def preview_convert_to_b2b(file: UploadFile, manufacturer: str = Form(None), force_manufacturer: bool = Form(False)):
    contents = await file.read()
    reader = build_reader(contents)

    type_map = {
        "carpet": "CAR", "carpet tile": "CARTIL",
        "vinyl": "VIN", "vinyl plank": "VINLVP",
        "wood": "WOO", "laminate": "LAM",
        "tile": "CER", "stone": "STO",
        "pad": "PAD", "rug": "RUG",
    }

    out = []
    for r in reader:
        original_manuf = (
            get_any(r, ["manufacturer", "vendor"])
            or r.get("DEALER")
            or r.get("SUPPLIER")
            or ""
        )

        if manufacturer:
            manuf = manufacturer.strip() if force_manufacturer else original_manuf or manufacturer.strip()
        else:
            manuf = original_manuf

        style = get_any(r, ["description", "style", "pattern"]) or ""
        color = get_any(r, ["color", "colour"]) or ""
        sku = get_any(r, ["sku", "ikey"]) or ""
        pricing_unit = normalize_unit(get_any(r, ["pc", "unit", "uom", "bu"]) or "")
        price = get_any(r, ["price", "cut cost", "base price"]) or ""

        product_type = resolve_product_type(r, type_map)

        out.append({
            "~~Manufacturer": manuf,
            "Style Name": style,
            "Color Name": color,
            "SKU": sku,
            "Product Type": product_type,
            "Pricing Unit": pricing_unit,
            "Cut Cost": price,
        })

    return {"already_b2b": False, "rows_preview": out[:200]}


# ----------------------------
# Convert to B2B CSV
# ----------------------------

@router.post("/convert-to-b2b")
async def convert_to_b2b(file: UploadFile, manufacturer: str = Form(None), force_manufacturer: bool = Form(False)):
    contents = await file.read()
    reader = build_reader(contents)

    headers = [
        "~~Manufacturer","Style Name","Style Number","Color Name","Color Number","SKU",
        "Product Type","Pricing Unit","Cut Cost","Roll Cost","Width/Quant-Carton","Backing",
        "Retail Price","Is Promo","Start Promo Date","End Promo Date","Promo Cut Cost","Promo Roll Cost",
        "Is Dropped","Retail Formula","Display Tags","Comments","Private Style","Private Color","Weight",
        "Custom","Style UX","Style CARE","Color CARE","Display Online","Freight","Picture 1 URL","Barcode"
    ]

    type_map = {
        "carpet": "CAR", "vinyl": "VIN", "vinyl plank": "VINLVP",
        "wood": "WOO", "laminate": "LAM", "tile": "CER", "stone": "STO",
        "pad": "PAD", "rug": "RUG",
    }

    output_rows = []

    for r in reader:
        original_manuf = get_any(r, ["manufacturer", "vendor"]) or r.get("DEALER") or r.get("SUPPLIER") or ""

        if manufacturer:
            manuf = manufacturer.strip() if force_manufacturer else original_manuf or manufacturer.strip()
        else:
            manuf = original_manuf

        style = (get_any(r, ["description", "style", "pattern"]) or "").strip()
        color = (get_any(r, ["color", "colour"]) or "").strip()
        sku = (get_any(r, ["sku", "ikey"]) or "").strip()
        pricing_unit = normalize_unit(get_any(r, ["pc", "unit", "uom", "bu"]) or "")
        price = get_any(r, ["price", "cut cost", "base price"]) or ""

        product_type = resolve_product_type(r, type_map)

        logger.info("Row SKU=%s type=%s unit=%s manuf=%s", sku, product_type, pricing_unit, manuf)

        output_rows.append({
            "~~Manufacturer": manuf or "Unknown Vendor",
            "Style Name": style,
            "Style Number": style[:80],
            "Color Name": color,
            "Color Number": color[:80],
            "SKU": sku,
            "Product Type": product_type,
            "Pricing Unit": pricing_unit,
            "Cut Cost": price,
            "Roll Cost": "",
            "Width/Quant-Carton": "",
            "Backing": "",
            "Retail Price": "",
            "Is Promo": "0",
            "Start Promo Date": "",
            "End Promo Date": "",
            "Promo Cut Cost": "",
            "Promo Roll Cost": "",
            "Is Dropped": "0",
            "Retail Formula": "",
            "Display Tags": "1",
            "Comments": "",
            "Private Style": "",
            "Private Color": "",
            "Weight": "",
            "Custom": "",
            "Style UX": "",
            "Style CARE": "",
            "Color CARE": "",
            "Display Online": "1",
            "Freight": "",
            "Picture 1 URL": "",
            "Barcode": "",
        })

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(output_rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=converted_b2b.csv"},
    )


# ----------------------------
# Export DB to JSON
# ----------------------------

@router.get("/export/json")
def export_b2b_json(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return {
        "products": [
            {
                "vendor": p.vendor.name if p.vendor else None,
                "sku": p.sku,
                "style": p.style,
                "color": p.color,
                "product_type": p.product_type,
                "pricing_unit": p.pricing_unit,
                "price": p.price,
                "currency": "USD",
            }
            for p in products
        ]
    }
