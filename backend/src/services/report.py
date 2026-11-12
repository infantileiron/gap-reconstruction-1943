import csv,io
from fastapi import HTTPException
from src.models.entities import Report
from src.config.settings import ARTIFACT_DIR
from src.utils import repository as repo
from src.utils.identity import new_id,now

def safe_cell(value):return "'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value
def list_reports():return repo.all_rows('reports')
def create(data):
 run,review=repo.get('runs',data.run_id),repo.get('reviews',data.review_id)
 if review['status']!='approved' or review['run_id']!=run['id'] or run['status']!='completed':raise ValueError('报告必须引用该运行批准复核')
 report=repo.put('reports',Report(new_id('rpt'),data.run_id,data.review_id,data.title,now()));ARTIFACT_DIR.mkdir(parents=True,exist_ok=True);(ARTIFACT_DIR/(report['id']+'.csv')).write_text(download(report['id']),encoding='utf-8');return report
def download(id):
 report=repo.get('reports',id);run=repo.get('runs',report['run_id']);r=run['result'];review=repo.get('reviews',report['review_id'])
 if review['status']!='approved':raise HTTPException(403,'复核未通过')
 out=io.StringIO();w=csv.writer(out);m=r['validation']['metrics']
 w.writerow(['report','station','points','missing','pchip_unfilled_gaps','q_per_hour','observation_r','validation_targets','common_count','rts_mae_common','pchip_mae_common','rts_observation_interval_coverage','checksum']);w.writerow([safe_cell(report['title']),safe_cell(r['station']),r['point_count'],r['missing_count'],r['pchip_unfilled_gaps'],r['study']['q_per_hour'],r['study']['observation_r'],m['target_count'],m['common_count'],m['rts_mae_common'],m['pchip_mae_common'],m['rts_observation_interval_coverage'],r['checksum']])
 w.writerow([]);fields=['time_hour','original_value','is_gap','rts_output','pchip_output','rts_mean','state_variance','observation_variance','state_low','state_high','observation_low','observation_high'];w.writerow(fields)
 for p in r['production']['series']:w.writerow([p[k] for k in fields])
 w.writerow([]);fields=['time_hour','validation_truth','training_value','rts_mean','pchip','state_variance','observation_variance','observation_low','observation_high'];w.writerow(fields)
 for p in r['validation']['targets']:w.writerow([p[k] for k in fields])
 return '\ufeff'+out.getvalue()
