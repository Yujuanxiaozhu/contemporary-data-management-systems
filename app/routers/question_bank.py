from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response

from app.core.database import get_db
from app.core.security import current_user, require_same_origin
from app.schemas.question_bank import CreateQuestion, CreateVersion, RestoreVersion, RepairLatest, ShareByUsername, ShareUpdate, ForkVersion
from app.services import question_bank as service

router = APIRouter(prefix='/api', tags=['question-bank'],
                   dependencies=[Depends(require_same_origin)])
Key = Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=128)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('/questions', status_code=201)
def create_question(data: CreateQuestion, key: Key, db=Depends(get_db), user=Depends(current_user)):
    return service.write(db, user, key, 'create', data.model_dump())


@router.get('/questions')
def list_questions(cursor: str | None = None, limit: Limit = 20,
                   status: Literal['active', 'archived'] = 'active',
                   db=Depends(get_db), user=Depends(current_user)):
    query = {'owner_id': user['_id'], 'status': status}
    if cursor:
        query['_id'] = {'$gt': service.oid(cursor)}
    # Filter before pagination: pending-only families must not consume page slots.
    rows = []
    for family in db.questions.find(query).sort('_id', 1):
        if service.has_committed_version(db, family):
            rows.append(family)
            if len(rows) == limit + 1:
                break
    return {'items': [service.family_out(db, f) for f in rows[:limit]],
            'next_cursor': str(rows[limit - 1]['_id']) if len(rows) > limit else None}


@router.get('/questions/{qid}')
def get_question(qid: str, db=Depends(get_db), user=Depends(current_user)):
    return service.family_out(db, service.visible_owned(db, qid, user))


@router.get('/questions/{qid}/versions')
def list_versions(qid: str, cursor: Annotated[int | None, Query(ge=1)] = None,
                  limit: Limit = 20, db=Depends(get_db), user=Depends(current_user)):
    family = service.visible_owned(db, qid, user)
    query = service.history(db, family, before=cursor)
    rows = list(query.sort('version_no', -1).limit(limit + 1))
    return {'items': [service.version_out(v) for v in rows[:limit]],
            'next_cursor': rows[limit - 1]['version_no'] if len(rows) > limit else None}


@router.get('/question-versions/{vid}')
def get_version(vid: str, db=Depends(get_db), user=Depends(current_user)):
    version = service.get_version(db, vid, user)
    family = db.questions.find_one({'_id': version['question_id'], 'owner_id': user['_id']})
    return service.version_out(version) if family else service.shared_version_out(version)


@router.post('/question-versions/{vid}/fork', status_code=201)
def fork_version(vid: str, data: ForkVersion, key: Key,
                 db=Depends(get_db), user=Depends(current_user)):
    return service.fork(db, user, key, vid, data.model_dump())


@router.post('/questions/{qid}/versions', status_code=201)
def create_version(qid: str, data: CreateVersion, key: Key,
                   db=Depends(get_db), user=Depends(current_user)):
    return service.write(db, user, key, 'version', data.model_dump(), qid)


@router.post('/questions/{qid}/restore', status_code=201)
def restore_version(qid: str, data: RestoreVersion, key: Key,
                    db=Depends(get_db), user=Depends(current_user)):
    return service.write(db, user, key, 'restore', data.model_dump(), qid)


@router.post('/questions/{qid}/repair-latest')
def repair_latest(qid: str, data: RepairLatest, db=Depends(get_db), user=Depends(current_user)):
    return service.repair_latest(db, qid, user, data.expected_revision)


@router.get('/stage2/operations/{opid}')
def get_operation(opid: str, db=Depends(get_db), user=Depends(current_user)):
    return service.operation_out(service.get_operation(db, opid, user))


@router.post('/stage2/operations/{opid}/resume')
def resume_operation(opid: str, db=Depends(get_db), user=Depends(current_user)):
    operation = service.get_operation(db, opid, user)
    result = service.execute(db, operation)
    return {**service.operation_out(service.get_operation(db, opid, user)), 'result': result}


@router.get('/shared-question-versions')
def shared_question_versions(cursor: str | None = None, limit: Limit = 20,
                             db=Depends(get_db), user=Depends(current_user)):
    from app.services import question_shares
    return question_shares.shared_versions(db, user, cursor, limit)


@router.put('/question-versions/{vid}/shares/{uid}')
def grant_version(vid: str, uid: str, response: Response, data: ShareUpdate, db=Depends(get_db), user=Depends(current_user)):
    from app.services import question_shares
    row, created = question_shares.grant(db, vid, uid, user, data.expected_revision)
    response.status_code = 201 if created else 200
    return question_shares.output(row)


@router.get('/question-versions/{vid}/shares')
def list_version_shares(vid: str, db=Depends(get_db), user=Depends(current_user)):
    from app.services import question_shares
    v = question_shares.owner_version(db, vid, user)
    rows=db.question_shares.find({'question_version_id':v['_id']}).sort('_id',1)
    return {'items':[{**question_shares.output(row), 'username': (db.users.find_one({'_id':row['grantee_user_id']},{'username':1}) or {}).get('username')} for row in rows]}


@router.delete('/question-versions/{vid}/shares/{uid}', status_code=204)
def revoke_version(vid: str, uid: str, expected_revision: Annotated[int | None, Query(ge=1)] = None, db=Depends(get_db), user=Depends(current_user)):
    from app.services import question_shares
    question_shares.revoke(db, vid, uid, user, expected_revision)
    return Response(status_code=204)


@router.post('/question-versions/{vid}/shares')
def grant_by_username(vid: str, data: ShareByUsername, response: Response,
                      db=Depends(get_db), user=Depends(current_user)):
    from app.services import question_shares
    question_shares.owner_version(db, vid, user)
    target=db.users.find_one({'username':data.username.strip()},{'_id':1})
    if target is None:service.fail(404,'resource_not_found')
    row,created=question_shares.grant(db,vid,str(target['_id']),user)
    response.status_code=201 if created else 200
    return question_shares.output(row)


@router.get('/questions/{qid}/usages')
def question_usages(qid: str, scope: Literal['all', 'current', 'historical'] = 'all',
                    version_id: str | None = None, cursor: str | None = None,
                    limit: Limit = 20, db=Depends(get_db), user=Depends(current_user)):
    from app.services import usage
    return usage.query(db, user, qid, scope, version_id, cursor, limit)


@router.get('/questions/{qid}/stats')
def cross_question_stats(qid: str, version_id: str | None = None,
                         scope: str = 'owned_surveys', db=Depends(get_db), user=Depends(current_user)):
    if scope != 'owned_surveys':
        service.fail(403, 'unsupported_statistics_scope')
    from app.services.cross_question_statistics import cross_question_statistics
    return cross_question_statistics(db, user, qid, version_id)
