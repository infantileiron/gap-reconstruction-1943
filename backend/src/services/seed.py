import random,math
from src.utils import repository as repo
from src.utils.identity import now
from src.utils.security import hash_password
from src.services.statistics import analyze

def demo_rows():
 rng=random.Random(2309);rows=[]
 for station,offset in [('LP-01',0),('LP-02',2),('LP-03',-1.2)]:
  walk=0
  for t in range(480):
   walk+=rng.gauss(0,.035);level=10+offset+1.3*math.sin(2*math.pi*t/48)+.003*t+walk;truth=round(level+rng.gauss(0,.22),5)
   missing=t<5 or 60<=t<=64 or 160<=t<=184 or t>=474 or station=='LP-02' and 330<=t<=333 or station=='LP-03' and 350<=t<=357
   rows.append({'station':station,'time_hour':float(t),'value':None if missing else truth,'truth':truth})
 return rows

def seed():
 repo.init_db()
 for role,name in [('admin','缺测复核工程师'),('analyst','测站数据分析员'),('viewer','环境观察员')]:
  email=f'{role}@lupu.test';repo.put('users',{'id':email,'email':email,'name':name,'role':role,'password_hash':hash_password('Gap2026!')},insert_only=True)
 rows=demo_rows();repo.put('datasets',{'id':'ds-stations','name':'三测站 · 480小时观测档案','source':'station_gaps_202611.csv','rows':rows,'created_at':now()},insert_only=True)
 mask={'id':'mask-block12','name':'LP-01连续遮挡100—111h','dataset_id':'ds-stations','station':'LP-01','start_hour':100.,'end_hour':111.,'target_times':[float(x) for x in range(100,112)],'created_at':now()};repo.put('masks',mask,insert_only=True)
 study={'id':'study-local-level','name':'固定q/r离线缺口复核','dataset_id':'ds-stations','mask_id':'mask-block12','q_per_hour':.03,'observation_r':.09,'initial_variance':10000.,'initial_level':None,'created_at':now()};repo.put('studies',study,insert_only=True)
 repo.put('runs',{'id':'run-demo','study_id':'study-local-level','status':'completed','result':analyze(rows,mask,study),'error':'','created_at':now()},insert_only=True)
 repo.put('reviews',{'id':'review-demo','run_id':'run-demo','comment':'RTS仅作离线重建；共用内点MAE与P+R观测覆盖已分开核验，原始观测不覆盖。','status':'approved','reviewer':'admin@lupu.test','created_at':now()},insert_only=True)
 repo.put('reports',{'id':'report-demo','run_id':'run-demo','review_id':'review-demo','title':'芦浦测站缺口与遮挡验证复核册','created_at':now()},insert_only=True)
 return {t:len(repo.all_rows(t)) for t in ('users','datasets','masks','studies','runs','reviews','reports')}
