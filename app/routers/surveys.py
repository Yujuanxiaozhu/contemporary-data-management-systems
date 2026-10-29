from fastapi import APIRouter, Depends, Response, Header
from app.core.database import get_db
from app.core.security import current_user, require_same_origin
from app.schemas.survey import SurveyInput, SurveyOut, survey_out
from app.services import jump_rules, questions, surveys
from app.schemas.binding import BindingInput, ReferenceInput
from app.services import draft_bindings, question_bank
router = APIRouter(prefix='/api/surveys', tags=['surveys'], dependencies=[Depends(require_same_origin)])

@router.get('', response_model=list[SurveyOut])
def list_surveys(user=Depends(current_user), db=Depends(get_db)):
    return [survey_out(s) for s in db.surveys.find({'owner_id': user['_id'], '_revision_deleted': {'$ne': True}}).sort('created_at', -1)]

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
def add_question(survey_id: str, data: dict, user=Depends(current_user), db=Depends(get_db),
                 idempotency_key: str | None = Header(default=None)):
    return survey_out(questions.add_question(db, survey_id, user, data, idempotency_key))


@router.put('/{survey_id}/questions/{question_id}', response_model=SurveyOut)
def update_question(survey_id: str, question_id: str, data: dict, user=Depends(current_user), db=Depends(get_db),
                    idempotency_key: str | None = Header(default=None)):
    return survey_out(questions.update_question(db, survey_id, question_id, user, data, idempotency_key))


@router.delete('/{survey_id}/questions/{question_id}', response_model=SurveyOut)
def delete_question(survey_id: str, question_id: str, user=Depends(current_user), db=Depends(get_db),
                    idempotency_key: str | None = Header(default=None)):
    return survey_out(questions.delete_question(db, survey_id, question_id, user, idempotency_key))


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
    result = {**{k: v for k, v in snapshot.items() if k not in ('_id', 'survey_id')},
              'survey_id': str(snapshot['survey_id'])}
    if 'question_bindings' in result:
        result['question_bindings'] = [draft_bindings.binding_out(b) for b in result['question_bindings']]
    return result


def _reference_write(db, survey_id, user, data, key, local_id=None):
    survey = questions._editable(db, survey_id, user)
    payload = {'local_id': local_id, 'body': data.model_dump()}
    action = 'reference' if local_id is None else 'binding'
    replay = draft_bindings.replay(db, survey, user, key, action, payload)
    if replay is not None:
        return survey_out(replay)
    if survey['schema_version'] != data.expected_schema_version:
        question_bank.fail(409, 'concurrent_modification')
    changes = draft_bindings.references(db, survey, user, data.question_version_id,
        data.required_override, getattr(data, 'order', None), local_id)
    questions._check_references(survey, changes['questions'])
    changes['_operation'] = {'key': key, 'action': action, 'payload': payload}
    return survey_out(questions.commit_structure(db, survey, user, changes))


@router.post('/{survey_id}/question-references', status_code=201, response_model=SurveyOut)
def add_reference(survey_id: str, data: ReferenceInput, user=Depends(current_user), db=Depends(get_db),
                  idempotency_key: str = Header(min_length=1, max_length=128)):
    return _reference_write(db, survey_id, user, data, idempotency_key)


@router.put('/{survey_id}/questions/{local_id}/binding', response_model=SurveyOut)
def update_binding(survey_id: str, local_id: str, data: BindingInput, user=Depends(current_user), db=Depends(get_db),
                   idempotency_key: str = Header(min_length=1, max_length=128)):
    return _reference_write(db, survey_id, user, data, idempotency_key, local_id)


def _owned_binding_operation(db, survey_id, operation_id, user):
    # Read status without triggering the owner's normal pending-help read path.
    if db.surveys.find_one(surveys.owned_filter(survey_id, user), {'_id': 1}) is None:
        question_bank.fail(404, 'resource_not_found')
    op = db.draft_operations.find_one({'_id': question_bank.oid(operation_id),
        'survey_id': question_bank.oid(survey_id), 'owner_id': user['_id']})
    if op is None:
        question_bank.fail(404, 'resource_not_found')
    return op


@router.get('/{survey_id}/binding-operations/{operation_id}')
def binding_operation(survey_id: str, operation_id: str, user=Depends(current_user), db=Depends(get_db)):
    op = _owned_binding_operation(db, survey_id, operation_id, user)
    current = db.surveys.find_one(surveys.owned_filter(survey_id, user))
    committed = op['state'] == 'COMMITTED' or op['_id'] in current.get('_binding_commits', [])
    result_version = op['base_schema'] + 1 if committed else None
    return {'operation_id': str(op['_id']), 'state': 'COMMITTED' if committed else op['state'],
            'result_schema_version': result_version, 'current_schema_version': current['schema_version'],
            'superseded': committed and current['schema_version'] > result_version}


@router.post('/{survey_id}/binding-operations/{operation_id}/resume', response_model=SurveyOut)
def resume_binding_operation(survey_id: str, operation_id: str, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(draft_bindings.execute(db, _owned_binding_operation(db, survey_id, operation_id, user)))


from app.schemas.revision import RevisionInput
from app.services import revisions


@router.post('/{survey_id}/revisions', status_code=201, response_model=SurveyOut)
def create_revision(survey_id: str, data: RevisionInput, user=Depends(current_user), db=Depends(get_db),
                    idempotency_key: str = Header(min_length=1, max_length=128)):
    return survey_out(revisions.create(db, survey_id, user, data.model_dump(), idempotency_key))


@router.get('/{survey_id}/revision-operations/{operation_id}')
def revision_operation(survey_id: str, operation_id: str, user=Depends(current_user), db=Depends(get_db)):
    op = revisions.get_operation(db, survey_id, operation_id, user)
    result = db.surveys.find_one({'_id': op['result_survey_id'], '_revision_operation_id': op['_id']})
    committed = op['state'] == 'COMMITTED' or (result is not None and not result.get('_revision_deleted'))
    return {'operation_id': str(op['_id']), 'state': 'COMMITTED' if committed else op['state'],
            'result_survey_id': str(op['result_survey_id']) if committed else None}


@router.post('/{survey_id}/revision-operations/{operation_id}/resume', response_model=SurveyOut)
def resume_revision(survey_id: str, operation_id: str, user=Depends(current_user), db=Depends(get_db)):
    return survey_out(revisions.execute(db, revisions.get_operation(db, survey_id, operation_id, user)))
