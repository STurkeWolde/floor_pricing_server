# app/backend/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.backend.database import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    contact = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    products = relationship("Product", back_populates="vendor")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, nullable=True)
    style = Column(String, nullable=True)
    color = Column(String, nullable=True)
    product_type = Column(String, nullable=True)
    pricing_unit = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    backing = Column(String, nullable=True)
    retail_price = Column(Float, nullable=True)
    is_promo = Column(Boolean, default=False)
    start_promo_date = Column(String, nullable=True)
    end_promo_date = Column(String, nullable=True)
    promo_cut_cost = Column(Float, nullable=True)
    promo_roll_cost = Column(Float, nullable=True)
    is_dropped = Column(Boolean, default=False)
    retail_formula = Column(String, nullable=True)
    display_tags = Column(Boolean, default=True)
    comments = Column(String, nullable=True)
    private_style = Column(String, nullable=True)
    private_color = Column(String, nullable=True)
    weight = Column(Float, nullable=True)
    custom = Column(String, nullable=True)
    style_ux = Column(String, nullable=True)
    style_care = Column(Float, nullable=True)
    color_care = Column(Float, nullable=True)
    display_online = Column(Boolean, default=True)
    freight = Column(Float, nullable=True)
    picture_url = Column(String, nullable=True)
    barcode = Column(String, nullable=True)

    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    vendor = relationship("Vendor", back_populates="products")
