"""Build the registry evidence slice from explicit official CSV snapshots."""
import csv, json, hashlib, collections, datetime, html
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCES={
 'projects':ROOT / 'projects.csv',
 'land':ROOT / 'land_registry.csv'}

def read(path):
 with path.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f); cols=reader.fieldnames; rows=list(reader)
 if not rows or any(None in r or any(v is None for v in r.values()) for r in rows):
  raise ValueError('Empty or malformed input: '+str(path))
 return cols,rows

def main():
 pc,projects=read(SOURCES['projects']);lc,lands=read(SOURCES['land'])
 by_property=collections.defaultdict(list)
 for land in lands:
  if land['property_id']: by_property[land['property_id']].append(land)
 selected=[r for r in projects if r['master_project_en']=='Al Furjan' or r['project_number']=='3189']
 if not selected: raise ValueError('No target records')
 output=[]
 for r in selected:
  matches=by_property[r['property_id']]
  land=matches[0] if len(matches)==1 else {}
  agrees=bool(land and land['project_id'] and land['project_id']==r['project_id'])
  review=[]
  if len(matches)!=1:review.append('Property key has '+str(len(matches))+' land matches')
  if not agrees:review.append('Project IDs missing or disagree')
  if not land.get('parcel_id'):review.append('No parcel identifier')
  if not land.get('munc_number'):review.append('No municipality plot number')
  output.append(dict(number=r['project_number'],name=land.get('project_name_en') or r['project_name'],
    name_original=r['project_name'],master=r['master_project_en'],area=r['area_name_en'],
    status=r['project_status'],reported_percent=r['percent_completed'],
    start=r['project_start_date'],planned_end=r['project_end_date'],completion_field=r['completion_date'],
    project_id=r['project_id'],property_id=r['property_id'],parcel_id=land.get('parcel_id',''),
    munc_number=land.get('munc_number',''),registry_area_m2=land.get('actual_area',''),
    villas=r['no_of_villas'],buildings=r['no_of_buildings'],description=r['project_description_en'],
    snapshot=r['load_timestamp'],land_snapshot=land.get('load_timestamp',''),
    match_count=len(matches),match_method='Exact property_id',project_id_agrees=agrees,
    match_assessment='KEYS_AGREE' if not review else 'REVIEW_REQUIRED',review=review,
    geometry_status='NOT_VERIFIED',satellite_status='NOT_EXTRACTED'))
 meta=dict(created=datetime.datetime.now(datetime.timezone.utc).isoformat(),project_rows=len(projects),land_rows=len(lands),
  project_columns=len(pc),land_columns=len(lc),furjan_rows=sum(x['master']=='Al Furjan' for x in output),
  sources={k:dict(path=str(v),sha256=hashlib.sha256(v.read_bytes()).hexdigest()) for k,v in SOURCES.items()},
  urls=['https://data.dubai/en/l/467654','https://data.dubai/en/l/465348'],
  status_counts=dict(collections.Counter(x['status'] for x in output if x['master']=='Al Furjan')),
  assessment_counts=dict(collections.Counter(x['match_assessment'] for x in output)),
  warnings=['Registry snapshot is not current observed construction state.','A land-record link is not a verified polygon.',
  'Completion field is not treated as verified handover.','Registry area can represent part of a community; never draw a polygon from its area alone.'])
 payload=json.dumps(dict(meta=meta,projects=output),ensure_ascii=False,indent=2)
 (ROOT/'registry-evidence.json').write_text(payload,encoding='utf-8')
 stamp=datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')
 (ROOT/('registry-run-'+stamp+'.md')).write_text('# Registry extraction and matching run\n\n'+json.dumps(meta,indent=2)+'\n\nScope authorised by Elan: demo and illustrated report; no external publication. Methods: incremental implementation, interface design and security. Raw sources preserved in Downloads; no secrets or escrow account numbers copied. Exact key matches are candidate record links, not calibrated spatial confidence. Next: verify boundaries and extract imagery.\n',encoding='utf-8')
 print(json.dumps({k:meta[k] for k in ['project_rows','land_rows','furjan_rows','status_counts','assessment_counts']},indent=2))

if __name__=='__main__':main()
