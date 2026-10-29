"""Recoverable draft occurrence commits; question versions use slice 1 exclusively."""
from copy import deepcopy
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.security import utcnow
from app.services import question_bank as bank
from app.services.validation import validate_question_definition


def structural_guard(survey):
    if survey['status'] != 'draft':
        bank.fail(409, 'published_frozen' if survey['status'] == 'published' else 'closed_readonly',
                  message='题目与跳转结构已冻结，请创建新草稿；原问卷和答卷保留。', next_action='create_draft')


def definition(question):
    return {k: v for k, v in question.items() if k not in ('id', 'order')}


def exact_match(left, right):
    """Use the immutable-version identity rule, including JSON 1 versus 1.0."""
    try:
        return bank.digest(left) == bank.digest(right)
    except (ValueError, TypeError):
        return False


def effective(version, override, local_id, order):
    if override is not None and type(override) is not bool:
        bank.fail(422, 'invalid_required_override')
    candidate = {**deepcopy(version['definition']), 'id': local_id, 'order': order}
    if override is not None:
        candidate['required'] = override
    result = validate_question_definition(candidate)
    if not result.valid:
        raise HTTPException(422, result.as_dict())
    return result.question


def option_fields(data):
    """Remove only explicitly supported optional fields from the old body."""
    data = dict(data)
    hints = {}
    for name in ('new_family', 'required_override'):
        if name in data:
            value = data.pop(name)
            if name == 'new_family' and type(value) is not bool:
                bank.fail(422, 'invalid_input')
            if name == 'required_override' and value is not None and type(value) is not bool:
                bank.fail(422, 'invalid_required_override')
            hints[name] = value
    return data, hints


def check_key(key):
    if key is not None and (not key or len(key) > 128 or
            any(ord(c) < 33 or ord(c) > 126 for c in key)):
        bank.fail(422, 'invalid_idempotency_key')


def request_hash(action, payload):
    try:
        return bank.digest({'action': action, 'body': payload})
    except (ValueError, TypeError):
        bank.fail(422, 'invalid_input')


def replay(db, survey, user, key, action, payload):
    structural_guard(survey)
    check_key(key)
    if key is None:
        return None
    op = db.draft_operations.find_one({'owner_id': user['_id'], 'survey_id': survey['_id'],
                                       'key': 'explicit:' + key})
    if op is None:
        return None
    if op['request_hash'] != request_hash(action, payload):
        bank.fail(409, 'idempotency_conflict')
    return execute(db, op)


def recent_replay(db, survey, action, payload):
    try:
        fingerprint = request_hash(action, payload)
    except HTTPException as exc:
        if exc.status_code == 422:
            # Let the old Validation Engine produce its established errors shape.
            return None
        raise
    op = db.draft_operations.find_one({'survey_id': survey['_id'], 'owner_id': survey['owner_id'],
        'state': 'COMMITTED', 'action': action, 'base_schema': survey['schema_version'] - 1,
        'request_hash': fingerprint})
    return result_survey(db, op) if op else None


def hints_unchanged(survey, local_id, hint):
    bindings = survey.get('question_bindings', [])
    if {b['local_question_id'] for b in bindings} != {q['id'] for q in survey['questions']}:
        return False
    bound = next((b for b in bindings if b['local_question_id'] == local_id), None)
    return bound is not None and ('required_override' not in hint or
                                 hint['required_override'] == bound.get('required_override'))


def reuse_plan(db, version, user, local, order, override):
    plan={'local_id':local, 'order':order, 'override':override, 'version_id':version['_id'], 'action':'reuse'}
    family=db.questions.find_one({'_id':version['question_id']})
    if family is None:bank.fail(404, 'resource_not_found')
    if family['owner_id'] != user['_id']:
        from app.services.question_shares import active
        grant=active(db, version['_id'], user)
        if grant is None:bank.fail(409, 'authorization_revoked')
        plan['share_id']=grant['_id'];plan['grant_epoch']=grant['grant_epoch']
    return plan


def plans_for(db, survey, user, changes):
    questions = deepcopy(changes.get('questions', survey['questions']))
    bindings = {b['local_question_id']: b for b in survey.get('question_bindings', [])}
    if len(bindings) != len(survey.get('question_bindings', [])):
        bank.fail(409, 'binding_mismatch')
    hints = changes.get('_binding_requests', {})
    plans = []
    for question in questions:
        local = question['id']
        hint = hints.get(local, {})
        bound = bindings.get(local)
        if 'question_version_id' in hint:
            version = bank.get_version(db, hint['question_version_id'], user)
            if bound and version['question_id'] != bound['question_id']:
                bank.fail(409, 'version_family_conflict')
            override = hint.get('required_override')
            resolved = effective(version, override, local, question['order'])
            if not exact_match(resolved, question):
                bank.fail(409, 'binding_mismatch')
            plans.append(reuse_plan(db, version, user, local, question['order'], override))
            continue
        if bound and not hint.get('new_family'):
            retained_revoked=False
            try:
                version = bank.get_version(db, str(bound['question_version_id']), user)
            except HTTPException as exc:
                # Permit removing revoked references one by one, while keeping all other data unchanged.
                is_delete=changes.get('_operation',{}).get('action')=='delete'
                revoked=db.question_shares.find_one({'question_version_id':bound['question_version_id'],
                                                      'grantee_user_id':user['_id'],'state':'REVOKED'})
                old_question=next((q for q in survey['questions'] if q['id']==local),None)
                if exc.status_code!=404 or not is_delete or revoked is None or old_question is None or not exact_match(definition(old_question),definition(question)):
                    raise
                version=db.question_versions.find_one({'_id':bound['question_version_id']})
                if not bank.committed(db,version):bank.fail(409,'binding_mismatch')
                retained_revoked=True
            if version['question_id'] != bound['question_id'] or version['content_hash'] != bound['content_hash']:
                bank.fail(409, 'binding_mismatch')
            override = bound.get('required_override')
            if 'required_override' in hint:
                override = hint['required_override']
            elif question['required'] != effective(version, override, local, question['order'])['required']:
                override = question['required'] if question['required'] != version['definition']['required'] else None
            content = {**definition(question), 'required': version['definition']['required']}
            effective({'definition': content}, override, local, question['order'])
            if exact_match(content, version['definition']):
                if retained_revoked:
                    plans.append({'local_id':local,'order':question['order'],'override':override,'version_id':version['_id'],
                                  'action':'reuse','retained_revoked':True})
                else:
                    plans.append(reuse_plan(db, version, user, local, question['order'], override))
            else:
                try:
                    family = bank.owned(db, str(version['question_id']), user)
                except HTTPException as exc:
                    if exc.status_code != 404:
                        raise
                    bank.fail(409, 'requires_fork', message='共享题不可修改原版本，请先创建自己的题目。')
                plans.append({'local_id': local, 'order': question['order'], 'override': override,
                    'action': 'version', 'question_id': str(family['_id']),
                    'body': {'definition': content, 'parent_version_id': str(version['_id']),
                             'expected_revision': family['revision']}})
        else:
            content = {**definition(question), 'required': hint.get('default_required', question['required'])}
            override = hint.get('required_override')
            effective({'definition': content}, override, local, question['order'])
            plans.append({'local_id': local, 'order': question['order'], 'override': override,
                          'action': 'create', 'body': {'definition': content}})
    return plans


def checkpoint(name, operation):
    """Fault-injection seam. No production action."""


def reject_deleted_revision(db, op, current):
    # The physical document can be either a retained barrier or already removed.
    # Read only: never complete, amend or remove the revision deletion marker.
    if current is not None and current.get('_revision_deleted'):
        bank.fail(410, 'revision_result_deleted', op['_id'])
    if current is None and db.revision_operations.find_one({
            'result_survey_id': op['survey_id'], 'owner_id': op['owner_id'],
            'result_deleted': True}, {'_id': 1}) is not None:
        bank.fail(410, 'revision_result_deleted', op['_id'])


def result_survey(db, op):
    current = db.surveys.find_one({'_id': op['survey_id'], 'owner_id': op['owner_id']})
    reject_deleted_revision(db, op, current)
    if current is None:
        bank.fail(404, 'resource_not_found')
    result_version = op['base_schema'] + 1
    if current['schema_version'] > result_version:
        bank.fail(409, 'operation_superseded', op['_id'], next_action='read_current_survey')
    # Binding metadata contains BSON IDs; compare its string-ID API projection.
    expected = {**op['resolved_changes'], 'question_bindings': [
        binding_out(b) for b in op['resolved_changes']['question_bindings']]}
    actual = {key: current.get(key) for key in expected}
    actual['question_bindings'] = [binding_out(b) for b in current.get('question_bindings', [])]
    if current['schema_version'] != result_version or not exact_match(actual, expected):
        bank.fail(409, 'operation_inconsistent', op['_id'])
    # Return one current document, never current metadata overlaid with old structure.
    return current


def execute(db, operation):
    opid = operation['_id']
    try:
        op = db.draft_operations.find_one({'_id': opid})
        survey = db.surveys.find_one({'_id': op['survey_id'], 'owner_id': op['owner_id']})
        reject_deleted_revision(db, op, survey)
        if survey is None:
            bank.fail(404, 'resource_not_found')
        if opid in survey.get('_binding_commits', []):
            result = result_survey(db, op)
            if op['state'] != 'COMMITTED':
                db.draft_operations.update_one({'_id': opid}, {'$set': {'state': 'COMMITTED'}})
            return result
        if op['state'] == 'FAILED':
            bank.fail(409, op['error_code'], opid)
        if op['state'] == 'COMMITTED':
            bank.fail(409, 'operation_inconsistent', opid)
        structural_guard(survey)
        pending = survey.get('_pending_binding')
        if pending != opid:
            if pending:
                bank.fail(409, 'operation_in_progress', opid)
            reserved = db.surveys.find_one_and_update(
                {'_id': survey['_id'], 'status': 'draft', 'schema_version': op['base_schema'],
                 '_pending_binding': {'$exists': False}, '_pending_schema': {'$exists': False}},
                {'$set': {'_pending_binding': opid}}, return_document=ReturnDocument.AFTER)
            if reserved is None:
                current = db.surveys.find_one({'_id': survey['_id']})
                reject_deleted_revision(db, op, current)
                if current is not None and opid in current.get('_binding_commits', []):
                    return execute(db, op)
                if current is None or current.get('_pending_binding') != opid:
                    db.draft_operations.update_one({'_id': opid},
                        {'$set': {'state': 'FAILED', 'error_code': 'concurrent_modification'}})
                    bank.fail(409, 'concurrent_modification', opid)
            checkpoint('reserved', op)
        if 'resolved_changes' not in op:
            bindings, questions = [], []
            for plan in op['plans']:
                if plan['action'] == 'reuse':
                    if plan.get('retained_revoked'):
                        if op['action']!='delete':bank.fail(409,'operation_inconsistent',opid)
                        version=db.question_versions.find_one({'_id':plan['version_id']})
                        if not bank.committed(db,version):bank.fail(409,'binding_mismatch',opid)
                    elif 'share_id' in plan:
                        from app.services import question_shares as shares
                        field=str(plan['share_id']);receipt=op.get('share_receipts',{}).get(field)
                        if receipt is None:
                            grant=db.question_shares.find_one({'_id':plan['share_id'],'grantee_user_id':op['owner_id'],
                                                              'question_version_id':plan['version_id']})
                            if grant is None:bank.fail(409, 'authorization_revoked', opid)
                            try:
                                receipt=shares.admit(db,{**grant,'grant_epoch':plan['grant_epoch']},opid,op['request_hash'])
                            except HTTPException as exc:
                                latest=db.draft_operations.find_one({'_id':opid})
                                receipt=(latest or {}).get('share_receipts',{}).get(field)
                                if receipt is None:
                                    if exc.status_code==409 and exc.detail.get('code')=='authorization_revoked':
                                        failed=db.draft_operations.update_one({'_id':opid,'state':'PREPARED','share_receipts.'+field:{'$exists':False}},{'$set':{'state':'FAILED','error_code':'authorization_revoked'}})
                                        if failed.matched_count:
                                            db.surveys.update_one({'_id':survey['_id'],'_pending_binding':opid},{'$unset':{'_pending_binding':''}})
                                            raise
                                        latest=db.draft_operations.find_one({'_id':opid})
                                        receipt=(latest or {}).get('share_receipts',{}).get(field)
                                    if receipt is None:raise
                            checkpoint('share_admitted',op)
                            db.draft_operations.update_one({'_id':opid},{'$set':{'share_receipts.'+field:receipt}})
                            op.setdefault('share_receipts',{})[field]=receipt
                        shares.forget_admission(db,plan['share_id'],opid)
                        version=db.question_versions.find_one({'_id':plan['version_id']})
                        if not bank.committed(db,version):bank.fail(409,'binding_mismatch',opid)
                    else:
                        version = bank.get_version(db, str(plan['version_id']), {'_id': op['owner_id']})
                else:
                    key = 'draft:' + str(opid) + ':' + plan['local_id']
                    try:
                        result = bank.write(db, {'_id': op['owner_id']}, key, plan['action'],
                                            plan['body'], plan.get('question_id'))
                    except HTTPException as exc:
                        if exc.status_code == 503:
                            bank.fail(503, 'operation_recovery_required', opid)
                        # Terminal family conflicts do not strand the draft indefinitely.
                        if exc.status_code == 409 and exc.detail.get('code') != 'operation_in_progress':
                            db.draft_operations.update_one({'_id': opid},
                                {'$set': {'state': 'FAILED', 'error_code': exc.detail['code']}})
                            db.surveys.update_one({'_id': survey['_id'], '_pending_binding': opid},
                                                  {'$unset': {'_pending_binding': ''}})
                        raise
                    version = bank.get_version(db, result['version']['question_version_id'], {'_id': op['owner_id']})
                question = effective(version, plan['override'], plan['local_id'], plan['order'])
                questions.append(question)
                bindings.append({'local_question_id': plan['local_id'], 'question_id': version['question_id'],
                    'question_version_id': version['_id'], 'required_override': plan['override'],
                    'content_hash': version['content_hash'], 'effective_hash': bank.digest(definition(question))})
                checkpoint('version_ready', op)
            resolved = {'questions': questions, 'question_bindings': bindings,
                        **({'jump_rules': op['jump_rules']} if 'jump_rules' in op else {})}
            # Resolve only predetermined payloads, then persist before the survey commit.
            if not exact_match(questions, op['questions']):
                bank.fail(409, 'binding_mismatch', opid)
            db.draft_operations.update_one({'_id': opid}, {'$set': {'resolved_changes': resolved}})
            op['resolved_changes'] = resolved
            checkpoint('resolved', op)
        updated = db.surveys.find_one_and_update(
            {'_id': survey['_id'], 'status': 'draft', 'schema_version': op['base_schema'],
             '_pending_binding': opid, '_pending_schema': {'$exists': False}},
            {'$set': {**op['resolved_changes'], 'updated_at': utcnow()}, '$inc': {'schema_version': 1},
             '$push': {'_binding_commits': opid}, '$unset': {'_pending_binding': ''}},
            return_document=ReturnDocument.AFTER)
        if updated is None:
            current = db.surveys.find_one({'_id': survey['_id']})
            reject_deleted_revision(db, op, current)
            if current is None or opid not in current.get('_binding_commits', []):
                bank.fail(409, 'concurrent_modification', opid)
        checkpoint('survey_committed', op)
        result = result_survey(db, op)
        db.draft_operations.update_one({'_id': opid}, {'$set': {'state': 'COMMITTED'}})
        return result
    except PyMongoError:
        bank.fail(503, 'operation_recovery_required', opid)


def commit(db, survey, user, changes, key=None, action='structure', payload=None):
    structural_guard(survey)
    check_key(key)
    fingerprint = request_hash(action, payload if payload is not None else changes)
    scope_key = 'explicit:' + key if key is not None else 'auto:' + str(survey['schema_version']) + ':' + fingerprint
    plans = plans_for(db, survey, user, changes)
    db.draft_operations.create_index([('owner_id', 1), ('survey_id', 1), ('key', 1)], unique=True)
    op = {'_id': ObjectId(), 'owner_id': user['_id'], 'survey_id': survey['_id'],
          'key': scope_key, 'action': action, 'request_hash': fingerprint, 'base_schema': survey['schema_version'],
          'state': 'PREPARED', 'plans': plans, 'questions': deepcopy(changes.get('questions', survey['questions'])),
          'created_at': utcnow()}
    if 'jump_rules' in changes:
        op['jump_rules'] = deepcopy(changes['jump_rules'])
    try:
        db.draft_operations.insert_one(op)
    except DuplicateKeyError:
        op = db.draft_operations.find_one({'owner_id': user['_id'], 'survey_id': survey['_id'], 'key': scope_key})
        if op['request_hash'] != fingerprint:
            bank.fail(409, 'idempotency_conflict')
    return execute(db, op)


def finish_pending(db, survey):
    if '_pending_binding' not in survey:
        return survey
    op = db.draft_operations.find_one({'_id': survey['_pending_binding'],
                                      'owner_id': survey['owner_id'], 'survey_id': survey['_id']})
    if op is None:
        bank.fail(409, 'operation_inconsistent')
    execute(db, op)
    current = db.surveys.find_one({'_id': survey['_id']})
    reject_deleted_revision(db, op, current)
    return current


def validate_publish(db, survey, user, granted_versions=None):
    if not survey['questions'] and not survey.get('question_bindings'):
        return
    if 'question_bindings' not in survey:
        bank.fail(409, 'legacy_binding_required')
    bindings = survey['question_bindings']
    if len(bindings) != len(survey['questions']) or len({b['local_question_id'] for b in bindings}) != len(bindings):
        bank.fail(409, 'binding_mismatch')
    by_local = {b['local_question_id']: b for b in bindings}
    for q in survey['questions']:
        b = by_local.get(q['id'])
        if b is None:
            bank.fail(409, 'binding_mismatch')
        if granted_versions is not None and b['question_version_id'] in granted_versions:
            version = db.question_versions.find_one({'_id': b['question_version_id']})
            if not bank.committed(db, version):bank.fail(409, 'binding_mismatch')
        else:
            version = bank.get_version(db, str(b['question_version_id']), user)
        if (version['question_id'] != b['question_id'] or version['content_hash'] != b['content_hash']
                or bank.digest(version['definition']) != version['content_hash']):
            bank.fail(409, 'binding_mismatch')
        expected = effective(version, b.get('required_override'), q['id'], q['order'])
        if (not exact_match(expected, q)
                or bank.digest(definition(expected)) != b['effective_hash']
                or not exact_match(definition(q), definition(expected))):
            bank.fail(409, 'binding_mismatch')
    from app.services.jump_rules import validate_jump_rules
    if not validate_jump_rules(survey['questions'], survey['jump_rules']).valid:
        bank.fail(409, 'rule_reference_conflict')


def references(db, survey, user, version_id, override, order, local_id=None):
    structural_guard(survey)
    version = bank.get_version(db, version_id, user)
    questions = deepcopy(survey['questions'])
    if local_id is None:
        if len(questions) >= 200:
            bank.fail(422, 'too_many_questions')
        local_id = uuid4().hex
        order = len(questions) + 1 if order is None else order
        if order > len(questions) + 1:
            bank.fail(422, 'invalid_order')
        questions.insert(order - 1, effective(version, override, local_id, order))
    else:
        index = next((i for i, q in enumerate(questions) if q['id'] == local_id), None)
        if index is None:
            bank.fail(404, 'resource_not_found')
        questions[index] = effective(version, override, local_id, questions[index]['order'])
    for i, q in enumerate(questions, 1):
        q['order'] = i
    return {'questions': questions, '_binding_requests': {local_id: {
        'question_version_id': version_id, 'required_override': override}}}


def binding_out(binding):
    return {k: str(v) if k in ('question_id', 'question_version_id') else v for k, v in binding.items()}
