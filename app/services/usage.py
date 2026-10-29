"""Owner-scoped, rebuildable usage projection; survey bindings remain authoritative."""
import base64
import hashlib
import json
from bson import ObjectId, json_util
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from app.core.security import utcnow
from app.services import question_bank as bank, draft_bindings as bindings, revisions


def checkpoint(name, *args):
    """Deterministic interruption seam for tests."""


def digest(value):
    return hashlib.sha256(json_util.dumps(value,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()


def indexes(db):
    db.usage_heads.create_index([('owner_id',1),('scope',1)],unique=True)
    db.usage_manifests.create_index([('generation_id',1),('source_key',1)],unique=True)
    db.question_usages.create_index([('generation_id',1),('source_key',1),('local_question_id',1)],unique=True)
    db.usage_generations.create_index([('owner_id',1),('scope',1),('state',1)])


def legacy_bindings(db,owner,survey,snapshot):
    """Only the already-approved committed revision conversion proves an old location."""
    questions=snapshot.get('questions',[])
    if not questions:return []
    ops=list(db.revision_operations.find({'owner_id':owner,'source_survey_id':survey['_id'],
        'source_schema_version':snapshot['schema_version'],'legacy':True,'state':'COMMITTED'}))
    try:expected=bank.digest(revisions.snapshot_payload(snapshot))
    except (KeyError,TypeError,ValueError):bank.fail(409,'source_inconsistent')
    mapped={}
    for op in ops:
        if op.get('source_hash')!=expected:bank.fail(409,'legacy_mapping_conflict')
        resolved=op.get('resolved_document') or {};bylocal={b.get('local_question_id'):b for b in resolved.get('question_bindings',[])}
        for plan in op.get('plans',[]):
            source=plan.get('source',{});local=source.get('local_question_id')
            if (source.get('owner_id')!=str(owner) or source.get('survey_id')!=str(survey['_id'])
                    or source.get('schema_version')!=snapshot['schema_version']):bank.fail(409,'legacy_mapping_conflict')
            q=next((x for x in questions if x.get('id')==local),None);b=bylocal.get(local)
            if (q is None or b is None or plan.get('key')!='revision-legacy:'+bank.digest(source)
                    or plan.get('source_hash')!=bank.digest(bindings.definition(q))):
                bank.fail(409,'legacy_mapping_conflict')
            version=db.question_versions.find_one({'_id':b.get('question_version_id')})
            if version is None or db.stage2_operations.find_one({'_id':version.get('operation_id'),
                    'owner_id':owner,'action':'create','key':plan['key'],'state':'COMMITTED'}) is None:
                bank.fail(409,'legacy_mapping_conflict')
            if local in mapped and mapped[local]!=b:bank.fail(409,'legacy_mapping_conflict')
            mapped[local]=b
    if set(mapped)!={q.get('id') for q in questions}:bank.fail(409,'legacy_mapping_required')
    return [mapped[q['id']] for q in questions]


def extract(db,owner,survey,source,historical):
    questions=source.get('questions')
    if (not isinstance(questions,list) or type(source.get('schema_version')) is not int or source['schema_version']<1
            or any(not isinstance(q,dict) or type(q.get('id')) is not str or not q['id']
                   or type(q.get('order')) is not int or q['order']<1 for q in questions)):
        bank.fail(409,'source_inconsistent')
    if sorted(q['order'] for q in questions)!=list(range(1,len(questions)+1)):bank.fail(409,'source_inconsistent')
    schema=source['schema_version'];kind='published_snapshot' if historical else 'current_binding'
    values=source.get('question_bindings')
    if values is None:
        if historical:
            try:values=legacy_bindings(db,owner,survey,source)
            except (KeyError,TypeError,ValueError,AttributeError):bank.fail(409,'source_inconsistent')
            kind='legacy_mapping'
        elif questions:bank.fail(409,'legacy_mapping_required')
        else:values=[]
    if not isinstance(values,list):bank.fail(409,'source_inconsistent')
    try:
        bylocal={b['local_question_id']:b for b in values}
        if len(bylocal)!=len(values) or len({q['id'] for q in questions})!=len(questions) or set(bylocal)!={q['id'] for q in questions}:bank.fail(409,'source_inconsistent')
        key=('snapshot:'+str(survey['_id'])+':'+str(schema)) if historical else ('draft:'+str(survey['_id']))
        rows=[]
        for q in questions:
            b=bylocal[q['id']];v=db.question_versions.find_one({'_id':b['question_version_id']})
            if (not bank.committed(db,v) or v['question_id']!=b['question_id'] or v['content_hash']!=b['content_hash']
                    or bank.digest(v['definition'])!=v['content_hash']):bank.fail(409,'source_inconsistent')
            effective=bindings.effective(v,b.get('required_override'),q['id'],q['order'])
            if not bindings.exact_match(effective,q) or bank.digest(bindings.definition(q))!=b['effective_hash']:
                bank.fail(409,'source_inconsistent')
            rows.append({'source_key':key,'owner_id':owner,'survey_id':survey['_id'],'survey_schema_version':schema,
                'survey_status':survey['status'],'question_id':b['question_id'],'question_version_id':b['question_version_id'],
                'local_question_id':q['id'],'position':q['order'],'source_kind':kind,'historical':historical})
    except (KeyError,TypeError,ValueError):bank.fail(409,'source_inconsistent')
    rows.sort(key=lambda x:(x['position'],x['local_question_id']))
    fingerprint=digest({'key':key,'schema':schema,'status':survey['status'],'questions':questions,'bindings':values,'rows':rows})
    return {'source_key':key,'source_hash':fingerprint,'rows':rows}


def sources(db,user,scope):
    if scope not in ('all','current','historical'):bank.fail(422,'invalid_scope')
    result=[]
    for survey in db.surveys.find({'owner_id':user['_id'],'_revision_deleted':{'$ne':True}}).sort('_id',1):
        status=survey.get('status')
        if status not in ('draft','published','closed'):bank.fail(409,'source_inconsistent')
        if survey.get('_pending_schema') or survey.get('_pending_binding'):bank.fail(409,'source_changed')
        if status=='draft' and scope in ('all','current'):
            result.append(extract(db,user['_id'],survey,survey,False))
        if status in ('published','closed') and scope in ('all','historical'):
            snapshots=list(db.survey_versions.find({'survey_id':survey['_id']}).sort('schema_version',1))
            schemas=[s.get('schema_version') for s in snapshots]
            if (any(type(value) is not int or value<1 for value in schemas)
                    or survey.get('schema_version') not in schemas or len(schemas)!=len(set(schemas))):
                bank.fail(409,'source_inconsistent')
            for response in db.responses.find({'survey_id':survey['_id']},{'survey_schema_version':1}):
                if response.get('survey_schema_version') not in schemas:bank.fail(409,'source_inconsistent')
            for snapshot in snapshots:
                if type(snapshot.get('schema_version')) is not int or snapshot['schema_version']>survey['schema_version']:
                    bank.fail(409,'source_inconsistent')
                result.append(extract(db,user['_id'],survey,snapshot,True))
    result.sort(key=lambda x:x['source_key']);return result


def source_digest(data):return digest([{'source_key':x['source_key'],'source_hash':x['source_hash']} for x in data])
def row_hash(rows):return digest(rows)


def check_generation(db,gen,data):
    manifests=list(db.usage_manifests.find({'generation_id':gen['_id']}))
    if len(manifests)!=len(data):bank.fail(409,'index_incomplete')
    bykey={m['source_key']:m for m in manifests}
    if len(bykey)!=len(manifests):bank.fail(409,'index_incomplete')
    total=0
    for src in data:
        m=bykey.get(src['source_key']);expected=src['rows']
        if m is None or m.get('state')!='READY' or m.get('source_hash')!=src['source_hash']:
            bank.fail(409,'index_incomplete')
        rows=list(db.question_usages.find({'generation_id':gen['_id'],'source_key':src['source_key']}))
        for row in rows:row.pop('_id',None);row.pop('generation_id',None)
        rows.sort(key=lambda x:(x['position'],x['local_question_id']))
        if m.get('expected_count')!=len(expected) or m.get('expected_hash')!=row_hash(expected) or len(rows)!=len(expected) or row_hash(rows)!=row_hash(expected):
            bank.fail(409,'index_incomplete')
        total+=len(rows)
    if db.question_usages.count_documents({'generation_id':gen['_id']})!=total:bank.fail(409,'index_incomplete')
    return total


def rebuild(db,user,scope='all'):
    indexes(db);uid=user['_id'];head=db.usage_heads.find_one({'owner_id':uid,'scope':scope});previous=head['active_generation'] if head else None
    gen={'_id':ObjectId(),'owner_id':uid,'scope':scope,'state':'BUILDING','created_at':utcnow()}
    db.usage_generations.insert_one(gen);activated=False
    try:
        checkpoint('generation_created',gen)
        data=sources(db,user,scope);sdigest=source_digest(data)
        for src in data:
            for row in src['rows']:
                db.question_usages.insert_one({'_id':ObjectId(),'generation_id':gen['_id'],**row})
                checkpoint('row_written',gen,row)
            db.usage_manifests.insert_one({'_id':ObjectId(),'generation_id':gen['_id'],'source_key':src['source_key'],
                'source_hash':src['source_hash'],'expected_count':len(src['rows']),'expected_hash':row_hash(src['rows']),'state':'READY'})
            checkpoint('source_written',gen,src)
        checkpoint('before_verify',gen)
        check_generation(db,gen,data)
        if source_digest(sources(db,user,scope))!=sdigest:bank.fail(409,'source_changed')
        checkpoint('after_verify',gen)
        if source_digest(sources(db,user,scope))!=sdigest:bank.fail(409,'source_changed')
        db.usage_generations.update_one({'_id':gen['_id'],'state':'BUILDING'}, {'$set':{'state':'READY','source_set_digest':sdigest,'source_count':len(data),'ready_at':utcnow()}})
        if head:
            updated=db.usage_heads.update_one({'_id':head['_id'],'active_generation':previous},{'$set':{'active_generation':gen['_id']}})
            if not updated.matched_count:bank.fail(409,'concurrent_modification')
        else:
            try:db.usage_heads.insert_one({'_id':ObjectId(),'owner_id':uid,'scope':scope,'active_generation':gen['_id']})
            except DuplicateKeyError:bank.fail(409,'concurrent_modification')
        activated=True
        return {'generation_id':str(gen['_id']),'source_count':len(data),'source_set_digest':sdigest}
    finally:
        if not activated:
            # A network error after the head CAS can leave its outcome unknown.
            # Never mark a generation FAILED when the durable head points to it.
            current=db.usage_heads.find_one({'owner_id':uid,'scope':scope})
            if current is None or current.get('active_generation')!=gen['_id']:
                db.usage_generations.update_one({'_id':gen['_id']},{'$set':{'state':'FAILED'}})


def permission(db,user,qid,version_id=None):
    qid=bank.oid(qid);family=db.questions.find_one({'_id':qid})
    if family is None:bank.fail(404,'resource_not_found')
    if family['owner_id']==user['_id'] and not bank.has_committed_version(db,family):bank.fail(404,'resource_not_found')
    allowed=None
    if family['owner_id']!=user['_id']:
        grants=db.question_shares.find({'question_id':qid,'grantee_user_id':user['_id'],'state':'ACTIVE'})
        allowed={g['question_version_id'] for g in grants}
        if not allowed:bank.fail(404,'resource_not_found')
    if version_id:
        v=bank.get_version(db,version_id,user)
        if v['question_id']!=qid:bank.fail(404,'resource_not_found')
        allowed={v['_id']}
    return qid,allowed


def query(db,user,qid,scope='all',version_id=None,cursor=None,limit=20):
    qid,allowed=permission(db,user,qid,version_id);data=sources(db,user,scope);sdigest=source_digest(data)
    head=db.usage_heads.find_one({'owner_id':user['_id'],'scope':scope})
    if head is None:bank.fail(409,'index_incomplete')
    gen=db.usage_generations.find_one({'_id':head['active_generation'],'owner_id':user['_id'],'scope':scope,'state':'READY'})
    if gen is None or gen.get('source_count')!=len(data) or gen.get('source_set_digest')!=sdigest:bank.fail(409,'index_incomplete')
    check_generation(db,gen,data)
    checkpoint('query_verified',gen)
    rows=list(db.question_usages.find({'generation_id':gen['_id'],'question_id':qid}))
    for row in rows:row.pop('_id',None);row.pop('generation_id',None)
    rows=[row for row in rows if allowed is None or row['question_version_id'] in allowed]
    rows.sort(key=lambda r:(str(r['survey_id']),r['survey_schema_version'],r['local_question_id'],str(r['question_version_id'])))
    cursor_scope=digest({'question_id':qid,'scope':scope,'version_id':version_id,'allowed':sorted(str(v) for v in allowed) if allowed is not None else None})
    offset=0
    if cursor:
        try:
            value=json.loads(base64.urlsafe_b64decode(cursor.encode()).decode());offset=value['offset']
            if value['generation']!=str(gen['_id']):bank.fail(409,'source_changed')
            if value['filter']!=cursor_scope:bank.fail(422,'invalid_cursor')
            if type(offset) is not int or offset<0 or offset>len(rows):raise ValueError()
        except HTTPException:raise
        except Exception:bank.fail(422,'invalid_cursor')
    # Check source coverage and authorization again before returning a page.
    if source_digest(sources(db,user,scope))!=sdigest:bank.fail(409,'source_changed')
    check_generation(db,gen,data)
    _,allowed2=permission(db,user,str(qid),version_id)
    if allowed2!=allowed:bank.fail(409,'source_changed')
    if db.usage_generations.find_one({'_id':gen['_id'],'owner_id':user['_id'],'scope':scope,'state':'READY',
            'source_set_digest':sdigest,'source_count':len(data)}) is None:bank.fail(409,'index_incomplete')
    if db.usage_heads.find_one({'_id':head['_id'],'active_generation':gen['_id']}) is None:bank.fail(409,'source_changed')
    nxt=offset+limit
    next_cursor=base64.urlsafe_b64encode(json.dumps({'generation':str(gen['_id']),'offset':nxt,'filter':cursor_scope}).encode()).decode() if nxt<len(rows) else None
    serial=[]
    for row in rows[offset:nxt]:
        serial.append({k:str(v) if isinstance(v,ObjectId) else v for k,v in row.items() if k not in ('owner_id','source_key')})
    return {'items':serial,'next_cursor':next_cursor,'index_state':'READY',
            'coverage':{'scope':scope,'source_count':len(data),'source_set_digest':sdigest,
                        'history_inventory':'existing_snapshots_and_response_references','consistency':'dynamic_non_transactional'}}
