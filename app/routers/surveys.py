from fastapi import APIRouter, Depends, Response
from app.core.database import get_db
from app.core.security import current_user, require_same_origin
from app.schemas.survey import SurveyInput, SurveyOut, survey_out
from app.services import jump_rules, questions, surveys
router = APIRouter(prefix='/api/surveys', tags=['surveys'], dependencies=[Depends(require_same_origin)])

@router.get('', response_model=list[SurveyOut])
def list_surveys(user=Depends(current_user), db=Depends(get_db)):
    return [survey_out(s) for s in db.surveys.find({'owner_id': user['_id']}).sort('created_at', -1)]

@router.post('', status_code=201, response_model=SurveyOut)
def create(data: SurveyInput, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(surveys.create_survey(db, user, data.model_dump()))

@router.get('/{survey_id}', response_model=SurveyOut)
def read(survey_id: str, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(surveys.get_owned(db, survey_id, user))

@router.put('/{survey_id}', response_model=SurveyOut)
def update(survey_id: str, data: SurveyInput, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(surveys.update_survey(db, survey_id, user, data.model_dump()))

@router.delete('/{survey_id}', status_code=204)
def delete(survey_id: str, user=Depends(current_user), db=Depends(get_db)):
    surveys.delete_survey(db, survey_id, user)
    return Response(status_code=204)

@router.post('/{survey_id}/publish', response_model=SurveyOut)
def publish(survey_id: str, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(surveys.transition(db, survey_id, user, 'published'))

@router.post('/{survey_id}/close', response_model=SurveyOut)
def close(survey_id: str, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(surveys.transition(db, survey_id, user, 'closed'))


@router.post('/{survey_id}/questions', status_code=201, response_model=SurveyOut)
def add_question(survey_id: str, data: dict, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(questions.add_question(db, survey_id, user, data))


@router.put('/{survey_id}/questions/{question_id}', response_model=SurveyOut)
def update_question(survey_id: str, question_id: str, data: dict, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(questions.update_question(db, survey_id, question_id, user, data))


@router.delete('/{survey_id}/questions/{question_id}', response_model=SurveyOut)
def delete_question(survey_id: str, question_id: str, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(questions.delete_question(db, survey_id, question_id, user))


@router.post('/{survey_id}/jump-rules', status_code=201, response_model=SurveyOut)
def add_jump_rule(survey_id: str, data: dict, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(jump_rules.add_rule(db, survey_id, user, data))


@router.put('/{survey_id}/jump-rules/{rule_id}', response_model=SurveyOut)
def update_jump_rule(survey_id: str, rule_id: str, data: dict, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(jump_rules.update_rule(db, survey_id, rule_id, user, data))


@router.delete('/{survey_id}/jump-rules/{rule_id}', response_model=SurveyOut)
def delete_jump_rule(survey_id: str, rule_id: str, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(jump_rules.delete_rule(db, survey_id, rule_id, user))


@router.get('/{survey_id}/versions/{schema_version}')
def read_version(survey_id: str, schema_version: int, user=Depends(current_user), db=Depends(get_db)):
    from app.services.versions import get_survey_version
    surveys.get_owned(db, survey_id, user)
    snapshot = get_survey_version(db, survey_id, schema_version)
    return {**{k: v for k, v in snapshot.items() if k not in ('_id', 'survey_id')},
            'survey_id': str(snapshot['survey_id'])}
