"""Explicit snapshot-to-new-draft creation, recoverable on standalone MongoDB."""
from copy import deepcopy

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.models.survey import new_survey
from app.services import draft_bindings as bindings, question_bank as bank
from app.services.jump_rules import validate_jump_rules
from app.services.surveys import owned_filter
from app.services.validation import validate_question_definition


def checkpoint(name, operation):
    """Fault injection only."""


def snapshot_payload(snapshot):
    result = {k: deepcopy(snapshot[k]) for k in ('questions', 'jump_rules')}
    if 'question_bindings' in snapshot:
        result['question_bindings'] = [bindings.binding_out(b) for b in snapshot['question_bindings']]
    return result


def validate_structure(snapshot):
    if (not isinstance(snapshot.get('questions'), list) or not isinstance(snapshot.get('jump_rules'), list)
            or any(not isinstance(q, dict) or type(q.get('id')) is not str or not q['id'] or 'order' not in q for q in snapshot['questions'])):
        bank.fail(409, 'revision_source_invalid')
    if 'question_bindings' in snapshot:
        required = {'local_question_id', 'question_id', 'question_version_id', 'content_hash', 'effective_hash'}
        values = snapshot['question_bindings']
        if (not isinstance(values, list) or any(not isinstance(b, dict) or not required <= b.keys()
                or type(b['local_question_id']) is not str or not b['local_question_id']
                or not isinstance(b['question_id'], ObjectId) or not isinstance(b['question_version_id'], ObjectId)
                or (b.get('required_override') is not None and type(b['required_override']) is not bool)
                for b in values)):
            bank.fail(409, 'revision_source_invalid')
    questions = snapshot['questions']
    if 'question_bindings' in snapshot:
        local_ids = [b['local_question_id'] for b in values]
        if len(set(local_ids)) != len(local_ids) or set(local_ids) != {q['id'] for q in questions}:
            bank.fail(409, 'revision_source_invalid')
    if len(questions) > 200 or len({q['id'] for q in questions}) != len(questions):
        bank.fail(409, 'revision_source_invalid')
    for order, q in enumerate(questions, 1):
        validated = validate_question_definition(q)
        if (not validated.valid or q['order'] != order
                or not bindings.exact_match(validated.question, q)):
            bank.fail(409, 'revision_source_invalid')
    if not validate_jump_rules(questions, snapshot['jump_rules']).valid:
        bank.fail(409, 'revision_source_invalid')


def get_operation(db, sid, opid, user):
    if db.surveys.find_one(owned_filter(sid, user), {'_id': 1}) is None:
        bank.fail(404, 'resource_not_found')
    op = db.revision_operations.find_one({'_id': bank.oid(opid),
        'owner_id': user['_id'], 'source_survey_id': bank.oid(sid)})
    if op is None:
        bank.fail(404, 'resource_not_found')
    return op


def cleanup_deleted(db, opid):
    # No new attempt can register once result_deleted is durable. Only attempts
    # registered before deletion can insert. Keep the same-_id barrier until
    # every such attempt has exited; a crashed attempt conservatively retains it.
    op = db.revision_operations.find_one({'_id': opid, 'result_deleted': True,
                                         'active_attempts': {'$size': 0}})
    if op is not None:
        db.surveys.delete_one({'_id': op['result_survey_id'], '_revision_deleted': True})


def deleted_result(db, op):
    db.revision_operations.update_one({'_id': op['_id']}, {'$set': {'result_deleted': True}})
    bank.fail(410, 'revision_result_deleted', op['_id'])


def execute(db, operation):
    opid, attempt = operation['_id'], ObjectId()
    registered = False
    try:
        # Atomic admission, never a check-then-insert: deletion closes admission.
        op = db.revision_operations.find_one_and_update(
            {'_id': opid, 'result_deleted': {'$ne': True}},
            {'$addToSet': {'active_attempts': attempt}}, return_document=ReturnDocument.AFTER)
        if op is None:
            cleanup_deleted(db, opid)
            bank.fail(410, 'revision_result_deleted', opid)
        registered = True
        return _execute_registered(db, op)
    except PyMongoError:
        bank.fail(503, 'operation_recovery_required', opid)
    finally:
        if registered:
            try:
                db.revision_operations.update_one({'_id': opid}, {'$pull': {'active_attempts': attempt}})
                cleanup_deleted(db, opid)
            except PyMongoError:
                # Unknown cleanup leaves a durable attempt/barrier, never opens
                # admission or risks resurrection. Explicit retries remain safe.
                pass


def _execute_registered(db, operation):
    opid = operation['_id']
    try:
        op = db.revision_operations.find_one({'_id': opid})
        current = db.surveys.find_one({'_id': op['result_survey_id'], 'owner_id': op['owner_id']})
        if current is not None:
            if current.get('_revision_deleted'):
                deleted_result(db, op)
            if current.get('_revision_operation_id') != opid:
                bank.fail(409, 'operation_inconsistent', opid)
            if op['state'] != 'COMMITTED':
                db.revision_operations.update_one({'_id': opid}, {'$set': {'state': 'COMMITTED'}})
            return current
        if op['state'] == 'COMMITTED':
            bank.fail(410, 'revision_result_deleted', opid)
        source = db.surveys.find_one({'_id': op['source_survey_id'], 'owner_id': op['owner_id']})
        snapshot = db.survey_versions.find_one({'survey_id': op['source_survey_id'],
                                                'schema_version': op['source_schema_version']})
        if source is None:
            bank.fail(404, 'resource_not_found')
        if source['status'] not in ('published', 'closed') or source.get('_pending_schema'):
            bank.fail(409, 'revision_source_unavailable', opid)
        if snapshot is None or bank.digest(snapshot_payload(snapshot)) != op['source_hash']:
            bank.fail(409, 'revision_source_changed', opid)
        if 'resolved_document' not in op:
            document = deepcopy(op['candidate'])
            if op['legacy']:
                document['question_bindings'] = []
                for q, plan in zip(document['questions'], op['plans']):
                    try:
                        result = bank.write(db, {'_id': op['owner_id']}, plan['key'], 'create',
                                            {'definition': bindings.definition(q)})
                    except HTTPException as exc:
                        if exc.status_code == 503:
                            bank.fail(503, 'operation_recovery_required', opid)
                        raise
                    v = bank.get_version(db, result['version']['question_version_id'], {'_id': op['owner_id']})
                    document['question_bindings'].append({'local_question_id': q['id'],
                        'question_id': v['question_id'], 'question_version_id': v['_id'],
                        'required_override': None, 'content_hash': v['content_hash'],
                        'effective_hash': bank.digest(bindings.definition(q))})
                    checkpoint('legacy_ready', op)
            bindings.validate_publish(db, document, {'_id': op['owner_id']})
            db.revision_operations.update_one({'_id': opid}, {'$set': {'resolved_document': document}})
            op['resolved_document'] = document
            checkpoint('resolved', op)
        checkpoint('before_survey_insert', op)
        try:
            db.surveys.insert_one(deepcopy(op['resolved_document']))
        except DuplicateKeyError:
            found = db.surveys.find_one({'_id': op['result_survey_id'], '_revision_operation_id': opid})
            if found is not None and found.get('_revision_deleted'):
                deleted_result(db, op)
            if found is None:
                bank.fail(409, 'revision_identity_conflict', opid)
        checkpoint('survey_inserted', op)
        db.revision_operations.update_one({'_id': opid}, {'$set': {'state': 'COMMITTED'}})
        checkpoint('committed', op)
        result = db.surveys.find_one({'_id': op['result_survey_id'], 'owner_id': op['owner_id']})
        if result is None or result.get('_revision_deleted'):
            deleted_result(db, op)
        return result
    except PyMongoError:
        bank.fail(503, 'operation_recovery_required', opid)


def create(db, sid, user, body, key):
    bindings.check_key(key)
    if key is None:
        bank.fail(422, 'invalid_idempotency_key')
    source = db.surveys.find_one(owned_filter(sid, user))
    if source is None:
        bank.fail(404, 'resource_not_found')
    request_hash = bank.digest(body)
    scope = {'owner_id': user['_id'], 'source_survey_id': source['_id'], 'key': key}
    opid = ObjectId(bank.digest({'owner': str(user['_id']), 'source': str(source['_id']), 'key': key})[:24])
    try:
        existing = db.revision_operations.find_one(scope)
    except PyMongoError:
        bank.fail(503, 'operation_recovery_required', opid)
    if existing:
        if existing['request_hash'] != request_hash:
            bank.fail(409, 'idempotency_conflict')
        return execute(db, existing)
    if source['status'] not in ('published', 'closed') or source.get('_pending_schema') or source.get('_pending_binding'):
        bank.fail(409, 'revision_source_unavailable')
    if body['expected_schema_version'] != source['schema_version'] or body['source_schema_version'] > source['schema_version']:
        bank.fail(409, 'concurrent_modification')
    snapshot = db.survey_versions.find_one({'survey_id': source['_id'],
                                           'schema_version': body['source_schema_version']})
    if snapshot is None:
        bank.fail(409, 'revision_snapshot_required')
    validate_structure(snapshot)
    legacy = 'question_bindings' not in snapshot
    if not legacy:
        bindings.validate_publish(db, snapshot, user)
    candidate = new_survey(user['_id'], {k: deepcopy(source[k]) for k in (
        'title', 'description', 'allow_anonymous', 'allow_multiple_submissions', 'deadline')})
    candidate.update({'_id': ObjectId(), 'revision_of': source['_id'],
        'revision_source_schema_version': body['source_schema_version'], '_revision_operation_id': opid,
        'questions': deepcopy(snapshot['questions']), 'jump_rules': deepcopy(snapshot['jump_rules'])})
    if not legacy:
        candidate['question_bindings'] = deepcopy(snapshot['question_bindings'])
    plans = []
    if legacy:
        for q in snapshot['questions']:
            origin = {'owner_id': str(user['_id']), 'survey_id': str(source['_id']),
                      'schema_version': body['source_schema_version'], 'local_question_id': q['id']}
            plans.append({'source': origin, 'source_hash': bank.digest(bindings.definition(q)),
                          'key': 'revision-legacy:' + bank.digest(origin)})
    try:
        db.revision_operations.create_index([('owner_id', 1), ('source_survey_id', 1), ('key', 1)], unique=True)
        db.revision_operations.create_index('result_survey_id', unique=True)
    except PyMongoError:
        bank.fail(503, 'operation_recovery_required', opid)
    op = {**scope, '_id': opid, 'request_hash': request_hash, 'state': 'PREPARED',
          'source_schema_version': body['source_schema_version'], 'source_hash': bank.digest(snapshot_payload(snapshot)),
          'candidate': candidate, 'result_survey_id': candidate['_id'], 'legacy': legacy, 'plans': plans}
    try:
        db.revision_operations.insert_one(op)
    except DuplicateKeyError:
        try:
            winner = db.revision_operations.find_one(scope)
        except PyMongoError:
            bank.fail(503, 'operation_recovery_required', opid)
        if winner is None:
            bank.fail(503, 'operation_recovery_required', opid)
        if winner['request_hash'] != request_hash:
            bank.fail(409, 'idempotency_conflict')
        op = winner
    except PyMongoError:
        bank.fail(503, 'operation_recovery_required', opid)
    try:
        stored = db.revision_operations.find_one({'_id': op['_id']})
        if stored is None:
            bank.fail(503, 'operation_recovery_required', op['_id'])
        op = stored
        checkpoint('prepared', op)
    except PyMongoError:
        bank.fail(503, 'operation_recovery_required', op['_id'])
    return execute(db, op)
