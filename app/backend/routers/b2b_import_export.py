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
    def clean_value(v):
        if isinstance(v, str):
            chars_to_remove = "()*[],"
            return ''.join(c for c in v if c not in chars_to_remove).strip()
        return v
    
    return {
        normalize_key(k): clean_value(v)
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


def parse_numeric(val) -> float | str:
    """Parse numeric values, return float if valid number, else empty string"""
    if val is None or val == "":
        return ""
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except Exception:
        return ""


def extract_retail_price(row: Dict, product_type: str) -> float | str:
    """
    Extract retail price intelligently:
    - If retail price field exists with a number, extract and return it as float
    - If retail price field exists but has no number, return it as text (material type)
    - If no retail price field found, return the product type as fallback
    """
    retail_price_raw = get_any(row, ["retail price", "retail", "msrp", "suggested price"])
    
    # If retail price field is found
    if retail_price_raw:
        # Try to extract a number from the string
        try:
            cleaned = str(retail_price_raw).replace("$", "").replace(",", "").strip()
            numeric_value = float(cleaned)
            return numeric_value
        except (ValueError, TypeError):
            # No number found, return the original value as material type text
            return str(retail_price_raw).strip()
    
    # No retail price field found, fall back to product type
    return product_type

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
        
        cols = re.split(r"[,\t;|]", line)
        cols = [c.strip() for c in cols]

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
    # 1️⃣ Decode safely
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    lines = text.splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="Empty CSV file")

    # 2️⃣ Find header row
    header_index = find_header_row(lines)
    relevant_lines = lines[header_index:]

    sample = "\n".join(relevant_lines[:10])

    # 3️⃣ Detect delimiter
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    logger.info(f"Detected delimiter: {delimiter}")

    # 4️⃣ Rebuild clean stream
    stream = io.StringIO("\n".join(relevant_lines))

    reader = csv.DictReader(stream, delimiter=delimiter)

    # 5️⃣ Normalize headers immediately
    reader.fieldnames = [normalize_key(h) for h in reader.fieldnames]

    logger.info("Normalized headers: %s", reader.fieldnames)

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
    "accessories" : "ACC",
    "castmetal" : "MET",
    "metal" : "MET",
    "LVT" : "VINTIL",
    "concrete" : "CON",
    "cement" : "CON",
    "terazzo" : "CON",
}


def resolve_product_type(row: Dict) -> str:
    material = (get_any(row, ["material type", "material", "surface"]) or "").lower()
    product_group = (get_any(row, ["product group", "group", "category"]) or "").lower()
    product_type_raw = (get_any(row, ["product type", "type"]) or "").lower()

    combined = f"{product_group} {material} {product_type_raw}"
    norm = normalize_key(combined)

    # ✅ 1. MATERIAL ALWAYS WINS (check specific materials first)
    if any(x in material for x in ["ceramic", "porcelain", "terracotta"]):
        return "CER"

    if any(x in material for x in ["marble", "travertine", "limestone", "granite", "onyx", "basalt", "slate"]):
        return "STO"

    if "glass" in material:
        return "GLS"

    if "lvt" in material:
        return "VINTIL"

    if "vinyl" in material:
        return "VIN"

    if "wood" in material:
        return "WOO"

    # ✅ 2. Then fallback to mapping
    for key, val in TYPE_MAP.items():
        if key.lower() in norm:
            return val

    # ✅ 3. Final fallback
    return "ACC"

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
        "sold by"
    ])
    if explicit:
        return normalize_unit(explicit)

    if product_type in {"CER", "STO", "STOTIL", "STOMOS", "VIN", "VINTIL", "LAM", "WOO"}:
        return "SF"

    if product_type == "PAD":
        return "SY"

    return "EA"


def extract_carton_quantity(row: Dict) -> str | float:
    """
    Extract carton/sheet quantity intelligently.
    
    Logic:
    - First check standard carton quantity fields (width/quant-carton, sf/cn, pcs/cn, etc.)
    - If none found, check sheet/unit size:
      - If contains dimensions (has 'x' or '×'): return 1
      - Otherwise: extract numeric value
    """
    # Check standard carton quantity fields first
    standard_fields = [
        "width/quant-carton",
        "sf/cn",
        "pcs/cn",
        "pcs/box",
        "pcs/sheet",
        "pcs/carton",
        "buy qty",
    ]
    
    result = get_any(row, standard_fields)
    if result and str(result).strip() not in ("", "0"):
        return result
    
    # Fall back to sheet/unit size
    sheet_size = get_any(row, ["sheet/unit size"])
    
    if not sheet_size:
        return ""
    
    sheet_size_str = str(sheet_size).strip().lower()
    
    # If sheet size contains dimensions (like "11.81x11.81" or "12.72x13.53"), return 1
    if 'x' in sheet_size_str or '×' in sheet_size_str:
        return 1
    
    # Otherwise, try to extract numeric value from sheet size
    # e.g., "25 LOOSE PIECES" -> 25, "6 LOOSE PIECES" -> 6
    import re
    match = re.search(r'(\d+(?:\.\d+)?)', sheet_size_str)
    if match:
        return float(match.group(1))
    
    return ""


def is_soho_pricelist(fieldnames: list[str]) -> bool:
    """
    Detect if this is a Soho pricelist by checking for Soho-specific columns.
    Soho lists typically have: COST/SF, COST-SHEET/BOX, and SF per SOLD BY columns.
    """
    normalized = [normalize_key(f) for f in fieldnames]
    has_cost_sf = any("costsf" in f for f in normalized)
    has_cost_sheet_box = any("costsheetbox" in f for f in normalized)
    has_sf_per_sold = any("sfpersold" in f for f in normalized)
    
    return has_cost_sf and has_cost_sheet_box and has_sf_per_sold


def extract_soho_pricing(row: Dict) -> tuple[str, float]:
    """
    Extract pricing unit and price for Soho price lists.
    
    Logic:
    - If COST/SF has a value: pricing_unit = "SF", price = COST/SF
    - If COST/SF is empty but COST-SHEET/BOX exists:
      pricing_unit = "EA", price = COST-SHEET/BOX / extract_carton_quantity(row)
      - If sheet/unit size has dimensions (e.g., "11.81x11.81"): divide by 1
      - If sheet/unit size has quantity (e.g., "25 LOOSE PIECES"): divide by 25
    - Otherwise: pricing_unit = "EA", price = COST-SHEET/BOX value
    
    Returns: (pricing_unit, price)
    """
    cost_sf = get_any(row, ["cost/sf", "cost/sf (box items)"])
    cost_sheet_box = get_any(row, ["cost-sheet/box", "cost sheet box"])
    
    # If COST/SF has a value, use it
    if cost_sf and str(cost_sf).strip() not in ("", "0"):
        return "SF", parse_price(cost_sf)
    
    # If COST/SF is empty but we have cost-sheet/box
    if cost_sheet_box and str(cost_sheet_box).strip() not in ("", "0"):
        cost_box_value = parse_price(cost_sheet_box)
        
        # Get the carton quantity from sheet/unit size
        carton_qty = extract_carton_quantity(row)
        
        if carton_qty and carton_qty != "":
            try:
                qty_value = float(carton_qty)
                if qty_value > 0:
                    calculated_price = cost_box_value / qty_value
                    return "EA", calculated_price
            except (ValueError, ZeroDivisionError, TypeError):
                pass
        
        # If we can't calculate, just use the box cost
        return "EA", cost_box_value
    
    # Default fallback
    return "EA", 0.0


def extract_weight(row: Dict) -> str:
    return get_any(row, [
        "weight", "wt", "weightlbs", "shippingweight", "grossweight", "lbs per carton"
    ]) or ""


def extract_soho_color(name: str) -> str:
    """
    Extract color from Soho product NAME.
    
    Soho typically formats as: "Brand Style [Color] SizeInfo"
    Examples:
    - "Angela Harris Florista Portobella Decor 8x8" → "Portobella"
    - "Ateno Bone Beige 12x24" → "Bone Beige"
    - "Fuego Canyon Terracotta 18x18" → "Canyon Terracotta"
    
    Strategy: Extract words before dimensional patterns (XxY, "x", "Mosaic", "Matte", etc.)
    """
    if not name:
        return ""
    
    name = str(name).strip()
    
    # Common dimension/finish patterns that mark end of color
    end_markers = [
        r'\d+x\d+',  # 12x24, 6x16, etc.
        r'\d+".*x.*\d+"',  # "7.87" x 7.87"
        r'\bmosaic\b',
        r'\bmatte\b',
        r'\bpolished\b',
        r'\bglossed?\b',
        r'\bsatin\b',
        r'\bhoned\b',
        r'\btumbled\b',
        r'\bfrosted\b',
        r'\bsemi-polished\b',
        r'\btextured\b',
        r'\bherringbone\b',
        r'\bstacked\b',
        r'\bbullnose\b',
        r'\bpencil\b',
        r'\bchevron\b',
        r'\bchair rail\b',
        r'\bkit only\b',
        r'\bkits?\b',
    ]
    
    # Find where the dimension/finish info starts
    import re
    end_pos = len(name)
    for pattern in end_markers:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            end_pos = min(end_pos, match.start())
    
    # Extract the color portion (before dimension markers)
    color_portion = name[:end_pos].strip()
    
    # Remove known brand/style prefixes from the start
    # Common Soho brand names to strip
    brands_styles = [
        "angela harris",
        "araminta",
        "ateno",
        "fuego",
        "janelle",
        "maisy",
        "malta",
        "mason",
        "metroville",
        "monarx",
        "nero dorato",
        "palmetto",
        "paula purroy",
        "pereto",
        "renoir",
        "sidra",
        "stacy garcia",
        "takami",
        "tectonic",
        "tessira",
        "tara",
        "accent",
        "accordion",
        "ages",
        "agoura",
        "alanis",
        "alchimia",
    ]
    
    for brand in brands_styles:
        if color_portion.lower().startswith(brand):
            color_portion = color_portion[len(brand):].strip()
            break
    
    # Remove style modifiers if they're at the end
    style_modifiers = [
        "decor", "mural", "frame", "deco", "floor", "mosaic",
        "checkerboard", "kit"
    ]
    
    for modifier in style_modifiers:
        pattern = rf'\b{modifier}\b'
        color_portion = re.sub(pattern, '', color_portion, flags=re.IGNORECASE).strip()
    
    # Clean up extra spaces
    color_portion = re.sub(r'\s+', ' ', color_portion).strip()
    
    return color_portion if color_portion else ""


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
    
    # Check if this is a Soho price list
    is_soho = is_soho_pricelist(reader.fieldnames or [])
    logger.info(f"Is Soho pricelist: {is_soho}")

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

        # Handle pricing based on pricelist type
        if is_soho:
            pricing_unit, price = extract_soho_pricing(row)
        else:
            price = parse_price(get_any(row, ["price", "cut cost", "base price", "distributor cost multiplier"]))
            pricing_unit = infer_pricing_unit(row, product_type)

        product = models.Product(
            sku=get_any(row, ["sku", "ikey", "code", "item #"]) or "",
            style=get_any(row, ["description", "style", "pattern", "name", "item description"]) or "",
            color=extract_soho_color(get_any(row, ["description", "style", "pattern", "name", "item description"]) or "") if is_soho else get_any(row, ["color", "colour"]) or "",
            product_type=product_type,
            pricing_unit=pricing_unit,
            price=price,
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
    
    # Check if this is a Soho price list
    is_soho = is_soho_pricelist(reader.fieldnames or [])
    logger.info(f"Is Soho pricelist: {is_soho}")

    out = []

    for raw_row in reader:
        row = normalize_row(raw_row)

        original_manuf = resolve_manufacturer(row)

        if manufacturer:
            manuf = manufacturer.strip() if force_manufacturer else original_manuf or manufacturer.strip()
        else:
            manuf = original_manuf

        product_type = resolve_product_type(row)

        # Handle pricing based on pricelist type
        if is_soho:
            pricing_unit, cut_cost = extract_soho_pricing(row)
        else:
            cut_cost = get_any(row, ["price", "cut cost", "base price", "retail price"]) or ""
            pricing_unit = infer_pricing_unit(row, product_type)

        # Extract color based on pricelist type
        if is_soho:
            style_name = get_any(row, ["description", "style", "pattern", "name", "item description"]) or ""
            color_name = extract_soho_color(style_name)
        else:
            style_name = get_any(row, ["description", "style", "pattern", "name", "item description"]) or ""
            color_name = get_any(row, ["color", "colour"]) or ""
        
        out.append({
            "~~Manufacturer": manuf,
            "Style Name": style_name,
            "Color Name": color_name,
            "SKU": get_any(row, ["sku", "ikey", "code", "item #"]) or "",
            "Product Type": product_type,
            "Pricing Unit": pricing_unit,
            "Cut Cost": cut_cost,
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
    
    # Check if this is a Soho price list
    is_soho = is_soho_pricelist(reader.fieldnames or [])
    logger.info(f"Is Soho pricelist: {is_soho}")

    headers = [
        "~~Manufacturer","Style Name","Style Number","Color Name","Color Number","SKU",
        "Product Type","Pricing Unit","Cut Cost","Roll Cost","Width/Quant-Carton","Backing",
        "Retail Price","Is Promo","Start Promo Date","End Promo Date","Promo Cut Cost","Promo Roll Cost",
        "Is Dropped","Retail Formula","Display Tags","Comments","Private Style","Private Color","Weight",
        "Custom","Style UX","Style CARE","Color CARE","Display Online","Freight","Picture 1 URL","Barcode"
    ]

    def clean_output_value(v):
        if isinstance(v, str):
            return v.replace("'", "").replace('"', "")
        return v

    output_rows = []

    for raw_row in reader:
        row = normalize_row(raw_row)

        original_manuf = resolve_manufacturer(row)

        if manufacturer:
            manuf = manufacturer.strip() if force_manufacturer else original_manuf or manufacturer.strip()
        else:
            manuf = original_manuf

        product_type = resolve_product_type(row)

        # Handle pricing based on pricelist type
        if is_soho:
            pricing_unit, cut_cost = extract_soho_pricing(row)
        else:
            # Standard pricing extraction
            cut_cost_raw = get_any(row, ["price", "cut cost", "base price", "distributor cost multiplier"]) or ""
            cut_cost = parse_numeric(cut_cost_raw)
            pricing_unit = infer_pricing_unit(row, product_type)
        
        # If single price provided, use it for both cut and roll cost
        roll_cost = cut_cost

        # Extract color based on pricelist type
        style_name = get_any(row, ["description", "style", "pattern", "name", "item description"]) or ""
        if is_soho:
            color_name = extract_soho_color(style_name)
        else:
            color_name = get_any(row, ["color", "colour"]) or ""
        
        output_row = {
            "~~Manufacturer": manuf or "Unknown Vendor",
            "Style Name": style_name,
            "Style Number": "",
            "Color Name": color_name,
            "Color Number": get_any(row, ["color number", "part / color #"]) or "",
            "SKU": get_any(row, ["sku", "ikey", "code", "item #"]) or "",
            "Product Type": product_type,
            "Pricing Unit": pricing_unit,
            "Cut Cost": cut_cost,
            "Roll Cost": roll_cost,
            "Width/Quant-Carton": parse_numeric(extract_carton_quantity(row)),
            "Backing": "",
            "Retail Price": extract_retail_price(row, product_type),
            "Is Promo": 0,
            "Start Promo Date": "",
            "End Promo Date": "",
            "Promo Cut Cost": "",
            "Promo Roll Cost": "",
            "Is Dropped": 0,
            "Retail Formula": "",
            "Display Tags": 0,
            "Comments": "",
            "Private Style": "",
            "Private Color": "",
            "Weight": parse_numeric(extract_weight(row)),
            "Custom": "",
            "Style UX": "",
            "Style CARE": "",
            "Color CARE": "",
            "Display Online": 0,
            "Freight": "",
            "Picture 1 URL": "",
            "Barcode": "",
        }

        # Clean single and double quotes from string values only
        output_row = {k: clean_output_value(v) if isinstance(v, str) else v for k, v in output_row.items()}

        output_rows.append(output_row)

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