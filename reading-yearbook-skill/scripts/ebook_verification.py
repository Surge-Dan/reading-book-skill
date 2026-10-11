"""Deterministic scheduling and strict contracts for batched-v1 verification."""
import copy
import hashlib
import json

STRATEGY='batched-v1'
MAX_CANDIDATES=16
MAX_EVIDENCE_CHARACTERS=24000

def encoded(value): return json.dumps(value,ensure_ascii=False,sort_keys=True)
def fail(): raise ValueError('batched-v1 候选、证据、代表或覆盖契约不符合要求')
def text(value): return isinstance(value,str) and bool(value.strip())
def strings(value): return isinstance(value,list) and all(text(x) for x in value)
def rows(value):
    if not isinstance(value,list) or any(not isinstance(x,dict) for x in value): fail()
    return value

def candidate_catalog(candidates):
    ids=[c['id'] for c in candidates]
    if len(ids)!=len(set(ids)): fail()
    return [{k:c[k] for k in ('id','type','title','summary','task_ids')}|{'element_ids':[s['element_id'] for s in c['sources']]} for c in candidates]

def validate_alignment(value,candidates):
    expected={c['id'] for c in candidates}; seen=[]
    for group in rows(value.get('groups')):
        ids=group.get('candidate_ids')
        if not strings(ids) or not ids or not text(group.get('reason')) or group.get('canonical_id') not in ids: fail()
        seen.extend(ids)
    if len(seen)!=len(set(seen)) or set(seen)!=expected or not strings(value.get('gaps')): fail()
    return value

def evidence_package(assigned,candidates,alignment,document,chunks):
    ids=set(assigned)
    for group in alignment['groups']:
        if ids.intersection(group['candidate_ids']): ids.update(group['candidate_ids'])
    related=[copy.deepcopy(c) for c in candidates if c['id'] in ids]
    elements=document['elements']; required={s['element_id'] for c in related for s in c['sources']}
    if sum(len(e['text']) for e in elements)<=12000: selected=elements
    else:
        positions={i for i,e in enumerate(elements) if e['element_id'] in required}
        positions={j for i in positions for j in (i-1,i,i+1) if 0<=j<len(elements)}
        selected=[e for i,e in enumerate(elements) if i in positions]
    if not required.issubset({e['element_id'] for e in selected}): fail()
    locations=[{'chunk_id':c['chunk_id'],'element_ids':[e['element_id'] for e in c['elements']]} for c in chunks if any(e['element_id'] in {x['element_id'] for x in selected} for e in c['elements'])]
    return {'assigned_ids':assigned,'candidates':related,'evidence_elements':selected,'chunk_locations':locations}

def verification_batches(candidates,alignment,document,chunks):
    result=[]; offset=0
    while offset<len(candidates):
        count=min(MAX_CANDIDATES,len(candidates)-offset)
        while True:
            package=evidence_package([c['id'] for c in candidates[offset:offset+count]],candidates,alignment,document,chunks)
            size=len(encoded(package))
            if size<=MAX_EVIDENCE_CHARACTERS or count==1: break
            count-=1
        package['evidence_characters']=size
        package['requires_budget_confirmation']=size>MAX_EVIDENCE_CHARACTERS
        result.append(package); offset+=count
    return result

def validate_batch(value,payload):
    expected=set(payload['assigned_ids']); found=[]; original={c['id']:c for c in payload['candidates']}
    for row in rows(value.get('candidates')):
        cid=row.get('id'); found.append(cid)
        if not text(cid) or cid not in expected or row.get('status') not in ('validated','reference','needs_review','rejected') or not text(row.get('reason')): fail()
        if not strings(row.get('task_ids')) or set(row['task_ids'])!=set(original[cid]['task_ids']): fail()
        sources=rows(row.get('sources'))
        if not sources: fail()
        for source in sources:
            if not all(text(source.get(k)) for k in ('element_id','quote','location')): fail()
        # Preserve every original citation; the pipeline's exact source gate then
        # checks all model citations against the actual document.
        if not {(s['element_id'],s['quote']) for s in original[cid]['sources']}.issubset({(s['element_id'],s['quote']) for s in sources}): fail()
        if row['status']=='validated':
            v=row.get('verification')
            if not isinstance(v,dict): fail()
            if not all(v.get(k) is True for k in ('V1','V2','V3')): fail()
            source=v.get('source_sufficiency'); walk=v.get('walkthrough')
            if not isinstance(source,dict) or not text(source.get('reason')) or not isinstance(walk,dict): fail()
            if not text(walk.get('input')) or not text(walk.get('output')) or not strings(walk.get('steps')) or not walk['steps'] or not text(walk.get('completion_standard')) or not text(v.get('task_utility')): fail()
        if row.get('canonical_id') is not None:
            if row['status']!='rejected' or not text(row['canonical_id']) or row['canonical_id'] not in original or row['canonical_id']==cid or not text(row.get('coverage_reason')): fail()
    if len(found)!=len(set(found)) or set(found)!=expected or not strings(value.get('gaps')): fail()
    dispositions={row['id']:row for row in value['candidates']}
    for row in value['candidates']:
        target=dispositions.get(row.get('canonical_id'))
        if target and target['status']=='rejected': fail()
    return value

def merge_verification(candidates,batches,closing,overview,gaps):
    original={c['id']:c for c in candidates}; decisions={}
    for batch in batches:
        for row in batch['candidates']:
            if row['id'] in decisions: fail()
            decisions[row['id']]=copy.deepcopy(row)
    if set(decisions)!=set(original): fail()
    adjusted=set()
    for change in rows(closing.get('adjustments')):
        if set(change)-{'id','status','reason','canonical_id','coverage_reason'}: fail()
        cid=change.get('id')
        if not text(cid) or cid not in decisions or cid in adjusted or not text(change.get('reason')): fail()
        adjusted.add(cid); status=change.get('status')
        if status not in ('validated','reference','needs_review','rejected') or (status=='validated' and decisions[cid]['status']!='validated'): fail()
        decisions[cid].update(change)
    for cid,row in decisions.items():
        canonical=row.get('canonical_id')
        if canonical is not None:
            if row['status']!='rejected' or not text(canonical) or canonical==cid or canonical not in decisions or decisions[canonical]['status']=='rejected' or decisions[canonical].get('canonical_id') or not text(row.get('coverage_reason')): fail()
            target=decisions[canonical]
            target['original_candidate_ids']=list(dict.fromkeys(target.get('original_candidate_ids',[canonical])+[cid]))
            for source in row['sources']:
                if source not in target['sources']: target['sources'].append(copy.deepcopy(source))
    audits=rows(closing.get('task_audit')); task_ids=[]
    for task in audits:
        task_ids.append(task.get('task_id')); ids=task.get('candidate_ids'); status=task.get('status')
        if not text(task.get('task_id')) or not strings(ids) or not set(ids).issubset(decisions) or not text(task.get('reason')) or status not in ('covered','reference','needs_review','missing'): fail()
        if status in ('covered','reference') and (not ids or any(decisions[c]['status']!=('validated' if status=='covered' else 'reference') for c in ids)): fail()
        if any(decisions[c]['status']=='rejected' for c in ids): fail()
    if len(task_ids)!=len(set(task_ids)) or set(task_ids)!={t['id'] for t in overview['key_tasks']} or not strings(closing.get('gaps')): fail()
    return {'candidates':[decisions[c['id']] for c in candidates],'task_audit':copy.deepcopy(audits),'gaps':list(dict.fromkeys(gaps+[g for b in batches for g in b['gaps']]+closing['gaps']))}

def fingerprint(candidates): return hashlib.sha256(encoded(candidates).encode()).hexdigest()
