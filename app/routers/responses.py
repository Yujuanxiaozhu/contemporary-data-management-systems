from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from app.core.config import ROOT
from app.core.database import get_db
from app.core.security import optional_user, require_same_origin
from app.schemas.response import ResponseOut
from app.services import responses

router = APIRouter(tags=['public'], dependencies=[Depends(require_same_origin)])
templates = Jinja2Templates(directory=ROOT / 'app/templates')


@router.get('/api/public/surveys/{public_token}')
def read_public(public_token: str, user=Depends(optional_user), db=Depends(get_db)):
    return responses.public_survey(db, public_token, user)


@router.post('/api/public/surveys/{public_token}/next')
def next_public(public_token: str, data: dict, user=Depends(optional_user), db=Depends(get_db)):
    return responses.next_question(db, public_token, user, data)


@router.post('/api/public/surveys/{public_token}/responses', status_code=201, response_model=ResponseOut)
def submit(public_token: str, data: dict, user=Depends(optional_user), db=Depends(get_db)):
    return responses.submit_response(db, public_token, user, data)


@router.get('/survey/{public_token}', include_in_schema=False)
def survey_page(public_token: str, request: Request, user=Depends(optional_user), db=Depends(get_db)):
    responses.get_open_survey(db, public_token, user)
    return templates.TemplateResponse(request=request, name='survey.html', context={'public_token': public_token})
