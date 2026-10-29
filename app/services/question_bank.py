"""Immutable question versions with recoverable single-family CAS commits.

Only these new collections are accessed. No survey migration or implicit binding.
An operation's COMMITTED marker is the visibility authority; latest is a cache.
"""
import hashlib
import json
from copy import deepcopy

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.security import utcnow
from app.core.database import ensure_question_indexes
from app.services.validation import validate_question_definition


def fail(status, code, operation_id=None, **extra):
    detail = {'code': code, 'message': code, **extra}
    if operation_id is not None:
        detail['operation_id'] = str(operation_id)
    raise HTTPException(status, detail)


def oid(value):
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        fail(422, 'invalid_id')
    return ObjectId(value)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def normalize(definition):
    if not isinstance(definition, dict) or set(definition) - {
            'type', 'title', 'required', 'options', 'validation'}:
        fail(422, 'invalid_definition')
    result = validate_question_definition({**definition, 'id': 'standalone', 'order': 1})
    if not result.valid:
        fail(422, 'invalid_definition', **result.as_dict())
    return {k: v for k, v in result.question.items() if k not in ('id', 'order')}


def owned(db, qid, user):
    family = db.questions.find_one({'_id': oid(qid), 'owner_id': user['_id']})
    if family is None:
        fail(404, 'resource_not_found')
    return family


def committed(db, version):
    return version is not None and db.stage2_operations.find_one(
        {'_id': version['operation_id'], 'state': 'COMMITTED'}) is not None


def get_version(db, vid, user):
    version = db.question_versions.find_one({'_id': oid(vid)})
    if version is None:
        fail(404, 'resource_not_found')
    family = db.questions.find_one({'_id': version['question_id']})
    if family is None:
        fail(404, 'resource_not_found')
    if family['owner_id'] != user['_id']:
        from app.services.question_shares import active
        if active(db, version['_id'], user) is None:
            fail(404, 'resource_not_found')
    if not committed(db, version):
        fail(404, 'resource_not_found')
    return version


def history(db, family, before=None):
    ops = [o['_id'] for o in db.stage2_operations.find(
        {'question_id': family['_id'], 'state': 'COMMITTED'}, {'_id': 1})]
    query = {'question_id': family['_id'], 'operation_id': {'$in': ops}}
    if before is not None:
        query['version_no'] = {'$lt': before}
    return db.question_versions.find(query)


def has_committed_version(db, family):
    return next(iter(history(db, family).limit(1)), None) is not None


def visible_owned(db, qid, user):
    family = owned(db, qid, user)
    if not has_committed_version(db, family):
        fail(404, 'resource_not_found')
    return family


def version_out(v):
    result = {'question_version_id': str(v['_id']), 'question_id': str(v['question_id']),
            'version_no': v['version_no'], 'definition': v['definition'],
            'default_required': v['definition']['required'], 'content_hash': v['content_hash'],
            'parent_version_id': str(v['parent_version_id']) if v['parent_version_id'] else None,
            'restored_from': str(v['restored_from']) if v['restored_from'] else None,
            'restored_from_version_id': str(v['restored_from']) if v['restored_from'] else None,
            'created_at': v['created_at'].isoformat()}
    if v.get('derived_from_version_id'):
        result['derived_from_version_id'] = str(v['derived_from_version_id'])
    return result


def shared_version_out(v):
    result = version_out(v)
    for key in ('parent_version_id', 'restored_from', 'restored_from_version_id'):
        result[key] = None
    result.pop('derived_from_version_id', None)
    return result


def family_out(db, f):
    versions = list(history(db, f).sort('version_no', -1))
    latest = versions[0] if versions else None
    actual = latest['_id'] if latest else None
    return {'question_id': str(f['_id']), 'owner_id': str(f['owner_id']),
            'status': f['status'], 'revision': f['revision'],
            'latest_version_id': str(f['latest_version_id']) if f['latest_version_id'] else None,
            'latest_pointer_valid': f['latest_version_id'] == actual and
                f['committed_version_no'] == (latest['version_no'] if latest else 0),
            'created_at': f['created_at'].isoformat(),
            'title': latest['definition']['title'] if latest else None,
            'type': latest['definition']['type'] if latest else None,
            'latest_version_no': latest['version_no'] if latest else None,
            'latest_committed_version_id': str(actual) if actual else None,
            'version_count': len(versions),
            'updated_at': (latest['created_at'] if latest else f['created_at']).isoformat()}


def operation_out(op):
    return {'operation_id': str(op['_id']), 'action': op['action'], 'state': op['state'],
            'retryable': op['state'] in ('PREPARED', 'COMMITTED'),
            'published_result': ({'question_id': str(op['question_id']),
                                  'question_version_id': str(op['version_id'])}
                                 if op['state'] == 'COMMITTED' else None),
            'error_code': op.get('error_code')}


def get_operation(db, opid, user):
    op = db.stage2_operations.find_one({'_id': oid(opid), 'owner_id': user['_id']})
    if op is None:
        fail(404, 'resource_not_found')
    return op


def checkpoint(name, operation):
    """Failure-injection seam; production performs no extra work here."""


def execute(db, op):
    """Replay the exact durable payload; never rebase or update a version."""
    opid, qid = op['_id'], op['question_id']
    try:
        op = db.stage2_operations.find_one({'_id': opid})
        if op['state'] == 'FAILED':
            fail(409, op['error_code'], opid)
        if op['action'] == 'fork' and op.get('share_requirement'):
            from app.services import question_shares as shares
            requirement = op['share_requirement']
            if not op.get('share_receipt'):
                grant = db.question_shares.find_one({'_id': requirement['share_id']})
                if grant is None:
                    fail(409, 'authorization_revoked', opid)
                receipt = shares.admit(db, {**grant, 'grant_epoch': requirement['grant_epoch']},
                                       opid, op['request_hash'])
                checkpoint('fork_admitted', op)
                db.stage2_operations.update_one({'_id': opid, 'request_hash': op['request_hash']},
                                                 {'$set': {'share_receipt': receipt}})
            shares.forget_admission(db, requirement['share_id'], opid)
        if op['action'] in ('create', 'fork'):
            family = {'_id': qid, 'owner_id': op['owner_id'], 'created_at': op['created_at'],
                      'status': 'active', 'latest_version_id': None, 'committed_version_no': 0,
                      'revision': 0, 'next_version_no': 1, '_pending_version': None}
            try:
                db.questions.insert_one(family)
            except DuplicateKeyError:
                pass
        f = db.questions.find_one({'_id': qid, 'owner_id': op['owner_id']})
        if f is None:
            fail(409, 'operation_inconsistent', opid)
        pending = f.get('_pending_version')
        if op['state'] != 'COMMITTED' and (not pending or pending['operation_id'] != opid):
            if pending:
                refreshed = db.stage2_operations.find_one({'_id': opid})
                if refreshed['state'] == 'COMMITTED':
                    return execute(db, refreshed)
                fail(409, 'operation_in_progress', opid)
            if f['revision'] != op['expected_revision']:
                refreshed = db.stage2_operations.find_one({'_id': opid})
                if refreshed['state'] == 'COMMITTED':
                    return execute(db, refreshed)
                db.stage2_operations.update_one({'_id': opid, 'state': 'PREPARED'},
                    {'$set': {'state': 'FAILED', 'error_code': 'concurrent_modification'}})
                fail(409, 'concurrent_modification', opid)
            pending = {'operation_id': opid, 'version_no': f['next_version_no']}
            reserved = db.questions.update_one(
                {'_id': qid, 'revision': f['revision'], 'next_version_no': f['next_version_no'],
                 '_pending_version': None},
                {'$set': {'_pending_version': pending}, '$inc': {'next_version_no': 1}})
            if not reserved.modified_count:
                # Another replayer may have reserved our exact operation.
                current = db.questions.find_one({'_id': qid})
                pending = current.get('_pending_version')
                if not pending or pending['operation_id'] != opid:
                    # An overlapping replay can have completed already.
                    refreshed = db.stage2_operations.find_one({'_id': opid})
                    if refreshed['state'] == 'COMMITTED':
                        return execute(db, refreshed)
                    fail(409, 'concurrent_modification', opid)
            checkpoint('reserved', op)
        if op['state'] != 'COMMITTED':
            v = {'_id': op['version_id'], 'question_id': qid,
                 'version_no': pending['version_no'], 'definition': op['definition'],
                 'content_hash': digest(op['definition']), 'created_at': op['created_at'],
                 'created_by': op['owner_id'], 'parent_version_id': op['parent_version_id'],
                 'restored_from': op['restored_from'], 'operation_id': opid}
            if op['action'] == 'fork':
                v['derived_from_version_id'] = op['derived_from_version_id']
            try:
                db.question_versions.insert_one(deepcopy(v))
            except DuplicateKeyError:
                existing = db.question_versions.find_one({'_id': op['version_id']})
                # BSON dates round to milliseconds; the operation is read back from BSON first.
                if existing != v:
                    fail(409, 'operation_inconsistent', opid)
            checkpoint('version_inserted', op)
            db.stage2_operations.update_one({'_id': opid, 'state': 'PREPARED'},
                                           {'$set': {'state': 'COMMITTED'}})
            checkpoint('committed', op)
        v = db.question_versions.find_one({'_id': op['version_id']})
        if v is None:
            fail(409, 'operation_inconsistent', opid)
        db.questions.update_one({'_id': qid, '_pending_version.operation_id': opid},
            {'$set': {'latest_version_id': v['_id'], 'committed_version_no': v['version_no'],
                      'revision': op['expected_revision'] + 1, '_pending_version': None}})
        checkpoint('finalized', op)
        return {'family': family_out(db, db.questions.find_one({'_id': qid})),
                'version': version_out(v), 'family_revision': op['expected_revision'] + 1,
                'operation_id': str(opid)}
    except PyMongoError:
        fail(503, 'operation_recovery_required', opid)


def write(db, user, key, action, body, qid=None):
    if not key or len(key) > 128 or not key.strip() or any(ord(c) < 33 or ord(c) > 126 for c in key):
        fail(422, 'invalid_idempotency_key')
    family = owned(db, qid, user) if qid else None
    qid = str(family['_id']) if family else None
    # Fingerprint the parsed request including path BEFORE normalization. No credentials.
    try:
        fingerprint = digest({'method': 'POST', 'action': action, 'resource': qid, 'body': body})
    except (ValueError, TypeError):
        fail(422, 'invalid_definition')
    scope = {'owner_id': user['_id'], 'action': action, 'key': key}
    existing = db.stage2_operations.find_one(scope)
    if existing:
        if existing['request_hash'] != fingerprint:
            fail(409, 'idempotency_conflict')
        return execute(db, existing)
    parent = restored = None
    if action == 'restore':
        source = get_version(db, body['source_version_id'], user)
        if source['question_id'] != family['_id']:
            fail(409, 'version_family_conflict')
        restored = source['_id']
        definition = source['definition']
        latest = next(iter(history(db, family).sort('version_no', -1).limit(1)), None)
        parent = latest['_id'] if latest else None
    else:
        definition = normalize(body['definition'])
        if family:
            source = get_version(db, body['parent_version_id'], user)
            if source['question_id'] != family['_id']:
                fail(409, 'version_family_conflict')
            parent = source['_id']
    expected = body.get('expected_revision', 0)
    if family and family['revision'] != expected:
        fail(409, 'concurrent_modification')
    ensure_question_indexes(db)
    op = {**scope, '_id': ObjectId(), 'question_id': family['_id'] if family else ObjectId(),
          'version_id': ObjectId(), 'request_hash': fingerprint, 'state': 'PREPARED',
          'definition': definition, 'expected_revision': expected, 'parent_version_id': parent,
          'restored_from': restored, 'created_at': utcnow()}
    try:
        db.stage2_operations.insert_one(op)
    except DuplicateKeyError:
        op = db.stage2_operations.find_one(scope)
        if op['request_hash'] != fingerprint:
            fail(409, 'idempotency_conflict')
    return execute(db, op)


def fork(db, user, key, vid, body):
    if not key or len(key) > 128 or not key.strip() or any(ord(c) < 33 or ord(c) > 126 for c in key):
        fail(422, 'invalid_idempotency_key')
    try:
        fingerprint = digest({'method': 'POST', 'action': 'fork', 'resource': vid, 'body': body})
    except (ValueError, TypeError):
        fail(422, 'invalid_definition')
    scope = {'owner_id': user['_id'], 'action': 'fork', 'key': key}
    existing = db.stage2_operations.find_one(scope)
    if existing:
        if existing['request_hash'] != fingerprint:
            fail(409, 'idempotency_conflict')
        return execute(db, existing)
    source = get_version(db, vid, user)
    family = db.questions.find_one({'_id': source['question_id']})
    requirement = None
    if family['owner_id'] != user['_id']:
        from app.services.question_shares import active
        grant = active(db, source['_id'], user)
        if grant is None:
            fail(404, 'resource_not_found')
        requirement = {'share_id': grant['_id'], 'grant_epoch': grant['grant_epoch']}
    definition = normalize(body['definition']) if body['definition'] is not None else source['definition']
    ensure_question_indexes(db)
    op = {**scope, '_id': ObjectId(), 'question_id': ObjectId(), 'version_id': ObjectId(),
          'request_hash': fingerprint, 'state': 'PREPARED', 'definition': definition,
          'expected_revision': 0, 'parent_version_id': None, 'restored_from': None,
          'derived_from_version_id': source['_id'], 'share_requirement': requirement,
          'created_at': utcnow()}
    try:
        db.stage2_operations.insert_one(op)
    except DuplicateKeyError:
        op = db.stage2_operations.find_one(scope)
        if op['request_hash'] != fingerprint:
            fail(409, 'idempotency_conflict')
    return execute(db, op)


def repair_latest(db, qid, user, expected):
    family = owned(db, qid, user)
    if family['revision'] != expected or family.get('_pending_version'):
        fail(409, 'concurrent_modification')
    latest = next(iter(history(db, family).sort('version_no', -1).limit(1)), None)
    if latest is None:
        fail(409, 'operation_inconsistent')
    result = db.questions.update_one({'_id': family['_id'], 'revision': expected,
        '_pending_version': None}, {'$set': {'latest_version_id': latest['_id'],
                                             'committed_version_no': latest['version_no']}})
    if not result.matched_count:
        fail(409, 'concurrent_modification')
    return family_out(db, owned(db, qid, user))
