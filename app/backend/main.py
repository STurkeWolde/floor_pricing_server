from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.backend.database import engine, Base
from app.backend.routers import products, vendors, pricelists, qfloors_import_export, b2b_import_export

# Create all tables (if using SQLAlchemy ORM)
Base.metadata.create_all(bind=engine)

# Initialize app
app = FastAPI(
    title="Floor Pricing API",
    description="Backend server for managing flooring products, vendors, and B2B/QFloors imports.",
    version="1.0.0"
)

# CORS configuration — allow frontend to connect
origins = [
    "http://localhost:3000",  # React frontend
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root route
@app.get("/")
def root():
    return {"message": "✅ Floor Pricing API is running. Visit /docs for API documentation."}

# Routers
app.include_router(products.router)
app.include_router(vendors.router)
app.include_router(pricelists.router)
app.include_router(qfloors_import_export.router)
app.include_router(b2b_import_export.router)

