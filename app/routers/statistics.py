from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.core.security import current_user
from app.services import statistics

router = APIRouter(prefix='/api/surveys', tags=['statistics'])


@router.get('/{survey_id}/stats')
def survey_statistics(survey_id: str, user=Depends(current_user), db=Depends(get_db)):
    return statistics.compute_survey_statistics(db, survey_id, user)


@router.get('/{survey_id}/questions/{question_id}/stats')
def question_statistics(survey_id: str, question_id: str, user=Depends(current_user), db=Depends(get_db)):
    return statistics.compute_single_question_statistics(db, survey_id, question_id, user)
