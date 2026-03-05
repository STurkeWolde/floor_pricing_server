# app/backend/routers/b2b_import_export.py

import csv
import io
import logging
import re
from typing import Dict

from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.backend import database, models

router = APIRouter(prefix="/b2b", tags=["B2B Import/Export"])

# ----------------------------
# Logger
# ----------------------------

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


# ============================================================
# -------------------- CORE HELPERS ---------------------------
# ============================================================

def safe_filename(name: str | None, default: str = "converted_b2b.csv") -> str:
    if not name:
        return default
    name = re.sub(r"[^\w\-\.]", "_", name.strip())
    if not name.lower().endswith(".csv"):
        name += ".csv"
    return name


def normalize_key(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().lower().lstrip("\ufeff")
    return re.sub(r"[^a-z0-9]", "", s)


def normalize_row(raw_row: Dict) -> Dict:
    """Normalize row keys once so matching never fails."""
    return {
        normalize_key(k): (v.strip() if isinstance(v, str) else v)
        for k, v in raw_row.items()
        if k
    }


def get_any(row: Dict, keys: list[str]):
    for k in keys:
        nk = normalize_key(k)
        if nk in row and row[nk] not in (None, ""):
            return row[nk]
    return None


def parse_price(val) -> float:
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except Exception:
        return 0.0


# ============================================================
# ---------------- CSV READER (SAFE) --------------------------
# ============================================================

def find_header_row(lines: list[str]) -> int:
    """
    Detect the most likely header row by scoring rows
    based on number of columns and presence of useful keywords.
    """
    best_score = 0
    best_index = 0

    KEYWORDS = [
        "sku", "item", "description", "price", "cost",
        "color", "size", "uom", "unit", "code"
    ]

    for i, line in enumerate(lines[:50]):
        cols = [c.strip() for c in line.split(",")]

        if len(cols) < 3:
            continue

        score = 0

        # Score for number of columns
        score += len(cols)

        # Score for meaningful header words
        for c in cols:
            cl = c.lower()
            for kw in KEYWORDS:
                if kw in cl:
                    score += 5

        if score > best_score:
            best_score = score
            best_index = i

    return best_index


def build_reader(contents: bytes) -> csv.DictReader:
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    lines = text.splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="Empty CSV file")

    header_index = find_header_row(lines)
    real_lines = lines[header_index:]

    reader = csv.DictReader(real_lines)
    logger.info("Detected headers: %s", reader.fieldnames)
    return reader


# ============================================================
# ---------------- BUSINESS LOGIC -----------------------------
# ============================================================

TYPE_MAP = {
    "carpet": "CAR",
    "carpettile": "CARTIL",
    "vinyl": "VIN",
    "vinyltile": "VINTIL",
    "wood": "WOO",
    "laminate": "LAM",
    "tile": "CER",
    "ceramic": "CER",
    "porcelain": "CER",
    "ceramic glazed" : "CER",
    "porcelain glazed" : "CER",
    "stone": "STO",
    "pad": "PAD",
    "rug": "RUG",
    "glass": "GLS",
    "stonetile": "STOTIL",
    "stonemosaic": "STOMOS",
}


def resolve_product_type(row: Dict) -> str:
    combined = " ".join([
        str(get_any(row, ["product group", "group", "category"]) or ""),
        str(get_any(row, ["material type", "material", "surface"]) or ""),
        str(get_any(row, ["product type", "type"]) or ""),
    ])

    norm = normalize_key(combined)

    for key, val in TYPE_MAP.items():
        if key in norm:
            return val

    if "ceramic" in norm or "porcelain" in norm:
        return "CER"

    return "CER"


def normalize_unit(u: str | None) -> str:
    if not u:
        return "EA"

    raw = str(u).strip().upper()
    if "/" in raw:
        raw = raw.split("/")[0]
    raw = raw.replace(".", "").replace(" ", "")

    synonyms = {
        "SQFT": "SF",
        "SFT": "SF",
        "SQYD": "SY",
        "EACH": "EA",
        "PC": "EA",
        "PCS": "EA",
        "CARTON": "CT",
        "BOX": "CT",
    }

    return synonyms.get(raw, raw)


def infer_pricing_unit(row: Dict, product_type: str) -> str:
    explicit = get_any(row, [
        "bu",  # Arley support
        "unit",
        "uom",
        "sold by u/m",
        "pricing unit",
    ])
    if explicit:
        return normalize_unit(explicit)

    if product_type in {"CER", "STO", "STOTIL", "STOMOS", "VIN", "VINTIL", "LAM", "WOO"}:
        return "SF"

    if product_type == "PAD":
        return "SY"

    return "EA"


def extract_carton_quantity(row: Dict) -> str:
    return get_any(row, [
        "width/quant-carton",
        "sf/cn",
        "pcs/cn",
        "pcs/box",
    ]) or ""


def extract_weight(row: Dict) -> str:
    return get_any(row, [
        "weight", "wt", "weightlbs", "shippingweight", "grossweight"
    ]) or ""

def resolve_manufacturer(row: Dict) -> str:
    return (
        get_any(row, [
            "manufacturer",
            "manufacturer name",
            "vendor",
            "vendor name",
            "supplier",
            "dealer",
            "brand",
            "mfg",
        ])
        or ""
    )


# ============================================================
# ---------------- IMPORT CSV --------------------------------
# ============================================================

@router.post("/import/csv")
async def import_b2b_csv(file: UploadFile, db: Session = Depends(get_db)):
    contents = await file.read()
    reader = build_reader(contents)

    count = 0

    for raw_row in reader:
        row = normalize_row(raw_row)

        vendor_name = resolve_manufacturer(row) or "Unknown Vendor"

        vendor = db.query(models.Vendor).filter_by(name=vendor_name).first()
        if not vendor:
            vendor = models.Vendor(name=vendor_name)
            db.add(vendor)
            db.commit()
            db.refresh(vendor)

        product_type = resolve_product_type(row)

        product = models.Product(
            sku=get_any(row, ["sku", "ikey", "code", "item #"]) or "",
            style=get_any(row, ["description", "style", "pattern", "name", "item description"]) or "",
            color=get_any(row, ["color", "colour"]) or "",
            product_type=product_type,
            pricing_unit=infer_pricing_unit(row, product_type),
            price=parse_price(get_any(row, ["price", "cut cost", "base price"])),
            vendor_id=vendor.id,
        )

        db.add(product)
        count += 1

    db.commit()

    return {"status": "✅ B2B CSV imported successfully", "imported": count}


# ============================================================
# ---------------- PREVIEW -----------------------------------
# ============================================================

@router.post("/preview", response_class=JSONResponse)
async def preview_convert_to_b2b(
    file: UploadFile,
    manufacturer: str = Form(None),
    force_manufacturer: bool = Form(False)
):
    contents = await file.read()
    reader = build_reader(contents)

    out = []

    for raw_row in reader:
        row = normalize_row(raw_row)

        original_manuf = resolve_manufacturer(row)

        if manufacturer:
            manuf = manufacturer.strip() if force_manufacturer else original_manuf or manufacturer.strip()
        else:
            manuf = original_manuf

        product_type = resolve_product_type(row)

        out.append({
            "~~Manufacturer": manuf,
            "Style Name": get_any(row, ["description", "style", "pattern", "name", "item description"]) or "",
            "Color Name": get_any(row, ["color", "colour"]) or "",
            "SKU": get_any(row, ["sku", "ikey", "code", "item #"]) or "",
            "Product Type": product_type,
            "Pricing Unit": infer_pricing_unit(row, product_type),
            "Cut Cost": get_any(row, ["price", "cut cost", "base price"]) or "",
            "Weight": extract_weight(row),
            "Width/Quant-Carton": extract_carton_quantity(row),
        })

    return {"already_b2b": False, "rows_preview": out[:200]}


# ============================================================
# ---------------- CONVERT -----------------------------------
# ============================================================

@router.post("/convert-to-b2b")
async def convert_to_b2b(
    file: UploadFile,
    manufacturer: str = Form(None),
    force_manufacturer: bool = Form(False),
    filename: str = Form(None),
):
    contents = await file.read()
    reader = build_reader(contents)

    headers = [
        "~~Manufacturer","Style Name","Style Number","Color Name","Color Number","SKU",
        "Product Type","Pricing Unit","Cut Cost","Roll Cost","Width/Quant-Carton","Backing",
        "Retail Price","Is Promo","Start Promo Date","End Promo Date","Promo Cut Cost","Promo Roll Cost",
        "Is Dropped","Retail Formula","Display Tags","Comments","Private Style","Private Color","Weight",
        "Custom","Style UX","Style CARE","Color CARE","Display Online","Freight","Picture 1 URL","Barcode"
    ]

    output_rows = []

    for raw_row in reader:
        row = normalize_row(raw_row)

        original_manuf = resolve_manufacturer(row)

        if manufacturer:
            manuf = manufacturer.strip() if force_manufacturer else original_manuf or manufacturer.strip()
        else:
            manuf = original_manuf

        product_type = resolve_product_type(row)

        output_rows.append({
            "~~Manufacturer": manuf or "Unknown Vendor",
            "Style Name": get_any(row, ["description", "style", "pattern", "name", "item description"]) or "",
            "Style Number": "",
            "Color Name": get_any(row, ["color", "colour"]) or "",
            "Color Number": "",
            "SKU": get_any(row, ["sku", "ikey", "code", "item #"]) or "",
            "Product Type": product_type,
            "Pricing Unit": infer_pricing_unit(row, product_type),
            "Cut Cost": get_any(row, ["price", "cut cost", "base price"]) or "",
            "Roll Cost": "",
            "Width/Quant-Carton": extract_carton_quantity(row),
            "Backing": "",
            "Retail Price": "",
            "Is Promo": "0",
            "Start Promo Date": "",
            "End Promo Date": "",
            "Promo Cut Cost": "",
            "Promo Roll Cost": "",
            "Is Dropped": "0",
            "Retail Formula": "",
            "Display Tags": "0",  # default false
            "Comments": "",
            "Private Style": "",
            "Private Color": "",
            "Weight": extract_weight(row),
            "Custom": "",
            "Style UX": "",
            "Style CARE": "",
            "Color CARE": "",
            "Display Online": "0",
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
        headers={"Content-Disposition": f'attachment; filename="{safe_filename(filename)}"'}
    )


# ============================================================
# ---------------- EXPORT JSON -------------------------------
# ============================================================

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