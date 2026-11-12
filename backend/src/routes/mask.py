from fastapi import APIRouter,Depends
from src.controllers import mask as controller
from src.schemas.entities import MaskInput
from src.services.auth import current,editor
router=APIRouter(prefix='/masks',tags=['masks'])
@router.get('')
def list_items(user=Depends(current)):return controller.list_items()
@router.post('',status_code=201)
def create(data:MaskInput,user=Depends(editor)):return controller.create(data)
