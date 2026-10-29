"""Owner-only cross-survey statistics over verified usage and immutable snapshots."""
from collections import defaultdict
from copy import deepcopy
from bson import ObjectId
from app.services import usage, question_bank as bank, statistics
from app.services.validation import validate_question_definition


def checked_usages(db,user,qid,version_id):
    rows=[];cursor=None;coverage=None
    while True:
        page=usage.query(db,user,qid,'all',version_id,cursor,100)
        if coverage is not None and page['coverage']!=coverage:bank.fail(409,'source_changed')
        coverage=page['coverage'];rows.extend(page['items']);cursor=page['next_cursor']
        if cursor is None:break
    return [r for r in rows if r['historical']],coverage


def checked_response_inventory(db,user):
    """Detect orphaned schema references even on a damaged owned draft."""
    inventory=[]
    for survey in db.surveys.find({'owner_id':user['_id'],'_revision_deleted':{'$ne':True}}):
        for response in db.responses.find({'survey_id':survey['_id']},{'survey_schema_version':1}):
            schema=response.get('survey_schema_version')
            if (type(schema) is not int or schema<1 or survey.get('status') not in ('published','closed')
                    or db.survey_versions.find_one({'survey_id':survey['_id'],'schema_version':schema},{'_id':1}) is None):
                bank.fail(409,'statistics_data_inconsistency',message='答卷历史快照缺失或问卷状态不一致。')
            inventory.append({'survey_id':survey['_id'],'response_id':response['_id'],'schema':schema})
    inventory.sort(key=lambda x:(str(x['survey_id']),str(x['response_id'])))
    return usage.digest(inventory)


def visible_versions(db,user,qid,version_id):
    qid_obj,allowed=usage.permission(db,user,qid,version_id)
    family=db.questions.find_one({'_id':qid_obj})
    if allowed is None:
        candidates=list(bank.history(db,family).sort('version_no',1))
    else:
        candidates=[db.question_versions.find_one({'_id':vid,'question_id':qid_obj}) for vid in allowed]
        candidates=[v for v in candidates if bank.committed(db,v)]
        candidates.sort(key=lambda v:(v['version_no'],str(v['_id'])))
    try:
        for version in candidates:
            definition=version['definition']
            if (bank.digest(definition)!=version['content_hash'] or
                    not validate_question_definition({**definition,'id':'statistics','order':1}).valid):
                bank.fail(409,'statistics_data_inconsistency')
    except (KeyError,TypeError,ValueError):bank.fail(409,'statistics_data_inconsistency')
    return candidates


def cross_question_statistics(db,user,qid,version_id=None):
    rows,coverage=checked_usages(db,user,qid,version_id)
    inventory=checked_response_inventory(db,user)
    versions=visible_versions(db,user,qid,version_id)
    version_digest=usage.digest([{'id':v['_id'],'version_no':v['version_no'],'content_hash':v['content_hash'],
                                 'definition':v['definition']} for v in versions])
    groups={str(v['_id']):{'question_version_id':str(v['_id']),'version_no':v['version_no'],
             'question_type':v['definition']['type'],'by_occurrence':[],'values':[],
             'counts':{o['id']:0 for o in v['definition']['options']},'answered':0,'definition':v['definition']} for v in versions}
    snapshots={};checks={}
    for row in rows:
        vid=row['question_version_id']
        if vid not in groups:bank.fail(409,'source_changed')
        key=(row['survey_id'],row['survey_schema_version'])
        if key not in snapshots:
            survey=db.surveys.find_one({'_id':ObjectId(key[0]),'owner_id':user['_id'],'status':{'$in':['published','closed']}})
            snapshot=db.survey_versions.find_one({'survey_id':ObjectId(key[0]),'schema_version':key[1]})
            if survey is None or snapshot is None:bank.fail(409,'statistics_data_inconsistency',message='答卷历史快照缺失。')
            documents=list(db.responses.find({'survey_id':survey['_id'],'survey_schema_version':key[1]}).sort('_id',1))
            try:computed=statistics.compute_version_statistics(snapshot,documents)
            except (statistics.DataConsistencyError,KeyError,TypeError,ValueError) as exc:
                bank.fail(409,'statistics_data_inconsistency',message=str(exc))
            snapshots[key]=(computed,snapshot,documents)
            checks[key]=(usage.digest(snapshot),usage.digest(documents))
        computed,snapshot,documents=snapshots[key]
        entry=next((e for e in computed['questions'] if e['question']['id']==row['local_question_id']),None)
        if entry is None or entry['question']['order']!=row['position']:bank.fail(409,'statistics_data_inconsistency')
        stat=entry['statistics'];group=groups[vid];group['answered']+=stat['answered_count']
        group['by_occurrence'].append({'survey_id':row['survey_id'],'survey_schema_version':key[1],
            'local_question_id':row['local_question_id'],'position':row['position'],'answered_count':stat['answered_count']})
        if stat['type'] in ('number','text'):group['values'].extend(stat['values'])
        else:
            for option in stat['options']:
                if option['option_id'] not in group['counts']:bank.fail(409,'statistics_data_inconsistency')
                group['counts'][option['option_id']]+=option['count']
    # Recheck every used response and snapshot; never fall back to a current schema.
    for key,(snapshot_hash,response_hash) in checks.items():
        current=db.survey_versions.find_one({'survey_id':ObjectId(key[0]),'schema_version':key[1]})
        current_responses=list(db.responses.find({'survey_id':ObjectId(key[0]),'survey_schema_version':key[1]}).sort('_id',1))
        if current is None or usage.digest(current)!=snapshot_hash or usage.digest(current_responses)!=response_hash:
            bank.fail(409,'source_changed')
    again,coverage2=checked_usages(db,user,qid,version_id)
    if again!=rows or coverage2!=coverage or checked_response_inventory(db,user)!=inventory:bank.fail(409,'source_changed')
    final_versions=visible_versions(db,user,qid,version_id)
    if usage.digest([{'id':v['_id'],'version_no':v['version_no'],'content_hash':v['content_hash'],
                      'definition':v['definition']} for v in final_versions])!=version_digest:bank.fail(409,'source_changed')
    result=[]
    for group in groups.values():
        definition=group.pop('definition');values=group.pop('values');counts=group.pop('counts');answered=group.pop('answered')
        kind=group['question_type'];stat={'type':kind,'answered_count':answered}
        if kind in ('single_choice','multiple_choice'):
            stat['options']=[{'option_id':o['id'],'label':o['label'],'count':counts[o['id']],
                **({'percentage':100.0*counts[o['id']]/answered if answered else 0.0} if kind=='single_choice' else {})} for o in definition['options']]
            if kind=='multiple_choice':stat['total_selections']=sum(counts.values())
        else:
            # Reuse the existing numeric precision and validation implementation.
            question={**deepcopy(definition),'id':'statistics','order':1,'required':False}
            try:stat=statistics.compute_question_statistics(question,values)
            except statistics.DataConsistencyError as exc:bank.fail(409,'statistics_data_inconsistency',message=str(exc))
            if kind=='number':stat['count']=stat['answered_count']
        group['statistics']=stat;group['answered_count']=stat['answered_count'];result.append(group)
    return {'question_id':str(qid),'scope':'owned_surveys','versions':result,'coverage':coverage,
            'unit':'有效回答次数'}
