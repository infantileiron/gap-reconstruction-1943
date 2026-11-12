from fastapi import APIRouter,Depends
from src.controllers import batch_review as controller
from src.schemas.entities import BatchReviewInput
from src.services.auth import current,editor
router=APIRouter(prefix="/batch-reviews",tags=["batch-reviews"])
@router.get("")
def list_items(user=Depends(current)): return controller.list_items()
@router.post("",status_code=201)
def create(data:BatchReviewInput,user=Depends(editor)): return controller.create(data,user)
@router.get("/{id}")
def detail(id:str,user=Depends(current)): return controller.detail(id)
@router.post("/{id}/resume")
def resume(id:str,user=Depends(editor)): return controller.resume(id)
