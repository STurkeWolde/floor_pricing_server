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

# simple logger
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


# helpers
def normalize_unit(u: str) -> str:
    if not u:
        return "EA"
    s = str(u).strip().lower()
    s = s.replace(".", "").replace(" ", "")
    # common synonyms
    synonyms = {
        "sf": "SF", "sqft": "SF", "squarefeet": "SF", "squarefeet": "SF", "sft": "SF",
        "sy": "SY", "sqyd": "SY", "syard": "SY",
        "lf": "LF", "linearfeet": "LF",
        "ea": "EA", "each": "EA", "pcs": "EA", "piece": "EA", "pieces": "EA",
        "ct": "CT", "carton": "CT",
    }
    return synonyms.get(s, "EA")


def resolve_product_type(row: dict, type_map: dict) -> str:
    # Try multiple cues: product_group + material_type, material_type, type, category...
    candidates = [
        row.get("product_group"),
        row.get("product group"),
        row.get("productgroup"),
        row.get("material_type"),
        row.get("material type"),
        row.get("materialtype"),
        row.get("product_type"),
        row.get("Product Type"),
        row.get("type"),
        row.get("Type"),
        row.get("material"),
    ]
    # combine group + material_type if both present
    pg = row.get("product_group") or row.get("Product Group")
    mt = row.get("material_type") or row.get("Material Type")
    if pg and mt:
        candidate = f"{pg} {mt}".strip().lower()
        if candidate in type_map:
            return type_map[candidate]

    for c in candidates:
        if not c:
            continue
        key = str(c).strip().lower()
        if key in type_map:
            return type_map[key]
    # fallback
    return "VIN"


# ----------------------------
# Import B2B CSV into DB
# ----------------------------
@router.post("/import/csv")
async def import_b2b_csv(file: UploadFile, db: Session = Depends(get_db)):
    contents = await file.read()
    lines = contents.decode(errors="ignore").splitlines()
    reader = csv.DictReader(lines)

    count = 0
    for row in reader:
        vendor_name = row.get("Vendor Name") or row.get("~~Manufacturer") or row.get("Manufacturer") or "Unknown Vendor"
        vendor = db.query(models.Vendor).filter_by(name=vendor_name).first()
        if not vendor:
            vendor = models.Vendor(name=vendor_name)
            db.add(vendor)
            db.commit()
            db.refresh(vendor)

        price = row.get("Cut Cost") or row.get("Base Price") or row.get("Retail Price") or 0
        try:
            price_f = float(price) if price != "" else 0.0
        except Exception:
            logger.warning("Invalid price %s, defaulting to 0", price)
            price_f = 0.0

        product = models.Product(
            sku=row.get("SKU", ""),
            style=row.get("Style Name") or row.get("Style", ""),
            color=row.get("Color Name") or row.get("Color", ""),
            product_type=row.get("Product Type") or "",
            pricing_unit=row.get("Pricing Unit") or "",
            price=price_f,
            vendor_id=vendor.id,
        )
        db.add(product)
        count += 1

    db.commit()
    logger.info("Imported %d products from B2B CSV", count)
    return {"status": "✅ B2B CSV imported successfully", "imported": count}


# ----------------------------
# Preview conversion (returns JSON) - frontend will call this
# ----------------------------
@router.post("/preview", response_class=JSONResponse)
async def preview_convert_to_b2b(file: UploadFile, manufacturer: str = Form(None), force_manufacturer: bool = Form(False)):
    contents = await file.read()
    lines = contents.decode(errors="ignore").splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="Empty CSV file")

    # detect B2B already
    first_line = lines[0].strip().split(",")[0].strip('"')
    if first_line == "~~Manufacturer":
        # return a small sample of first N rows
        reader = csv.DictReader(lines)
        rows = [r for _, r in zip(range(10), reader)]
        return {"already_b2b": True, "sample": rows}

    reader = csv.DictReader(lines)

    # mapping dictionaries (extend as needed)
    type_map = {
        "carpet": "CAR", "carpet tile": "CARTIL", "tile": "CER", "ceramic": "CER",
        "vinyl": "VIN", "vinyl plank": "VINLVP", "vinyl tile": "VINTIL",
        "wood": "WOO", "laminate": "LAM", "pad": "PAD", "rug": "RUG", "stone": "STO",
        # combined keys (product_group material_type)
        "hard surface vinyl": "VIN", "resilient vinyl": "VIN", "luxury vinyl plank": "VINLVP",
        "wood engineered": "WOO",
    }

    out: List[dict] = []
    for r in reader:
        # extract fields robustly
        manufacturer_row = (r.get("~~Manufacturer") or r.get("Manufacturer") or r.get("Vendor") or r.get("Vendor Name") or "").strip()
        if not manufacturer_row and manufacturer and force_manufacturer:
            manufacturer_row = manufacturer.strip()
        elif not manufacturer_row and manufacturer and not force_manufacturer:
            # will only fill when empty later in convert; preview shows both possibilities
            manufacturer_row = ""

        style = r.get("Style") or r.get("Style Name") or r.get("Description") or ""
        color = r.get("Color") or r.get("Color Name") or ""
        sku = r.get("SKU") or r.get("Sku") or ""
        product_type = resolve_product_type(r, type_map)
        pricing_unit = normalize_unit(r.get("Pricing Unit") or r.get("Unit") or r.get("Unit Type") or "")
        price = r.get("Base Price") or r.get("Cut Cost") or r.get("Price") or ""
        out_row = {
            "~~Manufacturer": manufacturer_row,
            "Style Name": style,
            "Color Name": color,
            "SKU": sku,
            "Product Type": product_type,
            "Pricing Unit": pricing_unit,
            "Cut Cost": price,
        }
        out.append(out_row)

    return {"already_b2b": False, "rows_preview": out[:200]}


# ----------------------------
# Convert -> CSV (download)
# ----------------------------
@router.post("/convert-to-b2b")
async def convert_to_b2b(
    file: UploadFile,
    manufacturer: str = Form(None),
    force_manufacturer: bool = Form(False),
):
    contents = await file.read()
    lines = contents.decode(errors="ignore").splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="Empty CSV file")

    # if already B2B — return original CSV as-is
    first_line = lines[0].strip().split(",")[0].strip('"')
    if first_line == "~~Manufacturer":
        return StreamingResponse(
            iter(["\n".join(lines)]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=already_b2b.csv"},
        )

    reader = csv.DictReader(lines)

    headers = [
        "~~Manufacturer","Style Name","Style Number","Color Name","Color Number","SKU",
        "Product Type","Pricing Unit","Cut Cost","Roll Cost","Width/Quant-Carton","Backing",
        "Retail Price","Is Promo","Start Promo Date","End Promo Date","Promo Cut Cost","Promo Roll Cost",
        "Is Dropped","Retail Formula","Display Tags","Comments","Private Style","Private Color","Weight",
        "Custom","Style UX","Style CARE","Color CARE","Display Online","Freight","Picture 1 URL","Barcode"
    ]

    type_map = {
        "carpet": "CAR", "carpet tile": "CARTIL", "tile": "CER", "ceramic": "CER",
        "vinyl": "VIN", "vinyl plank": "VINLVP", "vinyl tile": "VINTIL",
        "wood": "WOO", "laminate": "LAM", "pad": "PAD", "rug": "RUG", "stone": "STO",
        "hard surface vinyl": "VIN", "resilient vinyl": "VIN", "luxury vinyl plank": "VINLVP",
        "wood engineered": "WOO",
    }
    # extend unit synonyms
    def norm_unit(u): 
        return normalize_unit(u)

    output_rows = []
    for r in reader:
        # manufacturer handling
        manuf = (r.get("~~Manufacturer") or r.get("Manufacturer") or r.get("Vendor") or r.get("Vendor Name") or "").strip()
        if not manuf and manufacturer:
            if force_manufacturer:
                manuf = manufacturer.strip()
                logger.info("Forcing manufacturer '%s' on all rows.", manuf)
            else:
                # manufacturer provided but not forced - only fill missing on row
                manuf = manufacturer.strip()

        style = (r.get("Style") or r.get("Style Name") or r.get("Description") or "").strip()
        color = (r.get("Color") or r.get("Color Name") or "").strip()
        sku = (r.get("SKU") or r.get("Sku") or "").strip()
        product_type = resolve_product_type(r, type_map)
        pricing_unit = norm_unit(r.get("Pricing Unit") or r.get("Unit") or "")
        price = r.get("Base Price") or r.get("Cut Cost") or r.get("Price") or ""
        width = r.get("Width") or r.get("Width/Quant-Carton") or 12

        # logging decisions
        logger.info("Row SKU=%s => type=%s unit=%s manufacturer=%s", sku, product_type, pricing_unit, manuf or "<empty>")

        out = {
            "~~Manufacturer": manuf or manufacturer or "Unknown Vendor",
            "Style Name": style,
            "Style Number": (style or "")[:80],
            "Color Name": color,
            "Color Number": (color or "")[:80],
            "SKU": sku,
            "Product Type": product_type,
            "Pricing Unit": pricing_unit,
            "Cut Cost": price or "",
            "Roll Cost": "",
            "Width/Quant-Carton": width,
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
            "Barcode": ""
        }
        output_rows.append(out)

    # build CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(output_rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=converted_b2b.csv"},
    )


# Export database products to JSON
@router.get("/export/json")
def export_b2b_json(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    data = [
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
    return {"products": data}
