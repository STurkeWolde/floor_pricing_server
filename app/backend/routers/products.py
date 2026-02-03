from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.backend import database, models, schemas

router = APIRouter(prefix="/products", tags=["Products"])

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.Product)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    try:
        db.commit()
    except:
        db.rollback()
        raise HTTPException(status_code=400, detail="Product already exists")
    db.refresh(db_product)
    return db_product

@router.get("/")
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).all()

@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"detail": "Product deleted successfully"}

@router.delete("/clear-all")
def clear_all_products(db: Session = Depends(get_db)):
    db.query(models.Product).delete()
    db.commit()
    return {"message": "All products deleted successfully"}