from typing import Annotated
from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app.core.database import get_db
from app.core.security import current_user, require_same_origin
from app.services import banks

router=APIRouter(prefix='/api/question-banks',tags=['question-banks'],dependencies=[Depends(require_same_origin)])
Key=Annotated[str,Header(alias='Idempotency-Key',min_length=1,max_length=128)]
Limit=Annotated[int,Query(ge=1,le=100)]
class BankCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    description:str=Field(default='',max_length=1000)
class BankUpdate(BankCreate):
    expected_revision:Annotated[StrictInt,Field(ge=1)]
class ItemCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question_version_id:str
class ItemUpdate(ItemCreate):
    expected_revision:Annotated[StrictInt,Field(ge=1)]

@router.get('')
def listing(cursor:str|None=None,limit:Limit=20,db=Depends(get_db),user=Depends(current_user)):
    return banks.list_banks(db,user,cursor,limit)
@router.post('',status_code=201)
def create(body:BankCreate,key:Key,db=Depends(get_db),user=Depends(current_user)):
    return banks.create(db,user,key,body.model_dump())
@router.get('/{bid}')
def get(bid:str,db=Depends(get_db),user=Depends(current_user)):
    return banks.bank_out(banks.owned(db,bid,user))
@router.put('/{bid}')
def update(bid:str,body:BankUpdate,db=Depends(get_db),user=Depends(current_user)):
    return banks.update(db,bid,user,body.model_dump())
@router.delete('/{bid}',status_code=204)
def remove(bid:str,expected_revision:Annotated[int|None,Query(ge=1)]=None,db=Depends(get_db),user=Depends(current_user)):
    banks.remove_bank(db,bid,user,expected_revision);return Response(status_code=204)
@router.get('/{bid}/items')
def list_items(bid:str,cursor:str|None=None,limit:Limit=20,db=Depends(get_db),user=Depends(current_user)):
    return banks.list_items(db,bid,user,cursor,limit)
@router.post('/{bid}/items')
def add_item(bid:str,body:ItemCreate,response:Response,db=Depends(get_db),user=Depends(current_user)):
    item,created=banks.add(db,bid,user,body.question_version_id);response.status_code=201 if created else 200;return item
@router.put('/{bid}/items/{qid}')
def update_item(bid:str,qid:str,body:ItemUpdate,db=Depends(get_db),user=Depends(current_user)):
    return banks.update_item(db,bid,qid,user,body.question_version_id,body.expected_revision)
@router.delete('/{bid}/items/{qid}',status_code=204)
def remove_item(bid:str,qid:str,expected_revision:Annotated[int|None,Query(ge=1)]=None,db=Depends(get_db),user=Depends(current_user)):
    banks.remove_item(db,bid,qid,user,expected_revision);return Response(status_code=204)
