from pydantic import BaseModel
from typing import Optional
from datetime import date


# ---------- Vendor Schemas ----------
class VendorBase(BaseModel):
    name: str


class VendorCreate(VendorBase):
    pass


class Vendor(VendorBase):
    id: int

    class Config:
        orm_mode = True


# ---------- Product Schemas ----------
class ProductBase(BaseModel):
    sku: Optional[str] = None
    style: str
    color: Optional[str] = None
    product_type: Optional[str] = None
    pricing_unit: Optional[str] = None
    price: Optional[float] = 0.0

    width: Optional[float] = None
    backing: Optional[str] = None
    retail_price: Optional[float] = None
    is_promo: Optional[bool] = False
    start_promo_date: Optional[date] = None
    end_promo_date: Optional[date] = None
    promo_cut_cost: Optional[float] = None
    promo_roll_cost: Optional[float] = None
    is_dropped: Optional[bool] = False
    retail_formula: Optional[float] = None
    display_tags: Optional[bool] = True
    comments: Optional[str] = None
    private_style: Optional[str] = None
    private_color: Optional[str] = None
    weight: Optional[float] = None
    custom: Optional[str] = None
    style_ux: Optional[str] = None
    style_care: Optional[float] = None
    color_care: Optional[float] = None
    display_online: Optional[bool] = True
    freight: Optional[float] = None
    picture_url: Optional[str] = None
    barcode: Optional[str] = None

    vendor_id: Optional[int] = None


class ProductCreate(ProductBase):
    pass


class Product(ProductBase):
    id: int
    vendor: Optional[Vendor] = None

    class Config:
        orm_mode = True
