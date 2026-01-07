from fastapi import APIRouter

router = APIRouter(prefix="/pricelists", tags=["Price Lists"])

@router.get("/")
def get_pricelists():
    return {"message": "Price list endpoints placeholder"}
