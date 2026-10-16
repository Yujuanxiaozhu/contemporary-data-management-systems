from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import ROOT
from app.core.database import get_db
from app.core.security import optional_user
from app.schemas.survey import survey_out
from app.services import statistics, surveys

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=ROOT / 'app/templates')


def render(request, name, user=None, **context):
    return templates.TemplateResponse(request=request, name=name, context={'username': user['username'] if user else None, **context})


@router.get('/register')
def register_page(request: Request):
    return render(request, 'account.html', mode='register')


@router.get('/login')
def login_page(request: Request):
    return render(request, 'account.html', mode='login')


@router.get('/dashboard')
def dashboard(request: Request, user=Depends(optional_user), db=Depends(get_db)):
    if user is None:
        return RedirectResponse('/login', status_code=303)
    documents = [survey_out(s) for s in db.surveys.find({'owner_id': user['_id']}).sort('created_at', -1)]
    return render(request, 'dashboard.html', user, surveys=documents)


@router.get('/surveys/new')
def create_page(request: Request, user=Depends(optional_user)):
    if user is None:
        return RedirectResponse('/login', status_code=303)
    return render(request, 'edit.html', user, survey=None)


@router.get('/surveys/{survey_id}/edit')
def edit_page(survey_id: str, request: Request, user=Depends(optional_user), db=Depends(get_db)):
    if user is None:
        return RedirectResponse('/login', status_code=303)
    survey = surveys.get_owned(db, survey_id, user)
    return render(request, 'edit.html', user, survey=jsonable_encoder(survey_out(survey)))


@router.get('/surveys/{survey_id}/stats')
def stats_page(survey_id: str, request: Request, user=Depends(optional_user), db=Depends(get_db)):
    if user is None:
        return RedirectResponse('/login', status_code=303)
    result = statistics.compute_survey_statistics(db, survey_id, user)
    return render(request, 'statistics.html', user, result=result, question_id=None)


@router.get('/surveys/{survey_id}/questions/{question_id}/stats')
def question_stats_page(survey_id: str, question_id: str, request: Request, user=Depends(optional_user), db=Depends(get_db)):
    if user is None:
        return RedirectResponse('/login', status_code=303)
    result = statistics.compute_single_question_statistics(db, survey_id, question_id, user)
    for version in result['versions']:
        version['questions'] = [{'question': version.pop('question'), 'statistics': version.pop('statistics')}]
    return render(request, 'statistics.html', user, result=result, question_id=question_id)
