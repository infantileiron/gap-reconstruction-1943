import csv,io,math
from dataclasses import asdict
from src.models.entities import ObservationDataset
from src.utils import repository as repo
from src.utils.identity import new_id,now
from src.constants.domain import MAX_ROWS,MAX_STATIONS,MIN_TIME_STEP_HOURS

def summary(item):return {k:v for k,v in item.items() if k!='rows'}|{'row_count':len(item['rows']),'stations':sorted({r['station'] for r in item['rows']}),'observed':sum(r['value'] is not None for r in item['rows']),'missing':sum(r['value'] is None for r in item['rows'])}
def list_datasets():return [summary(x) for x in repo.all_rows('datasets')]
def detail(id):return repo.get('datasets',id)
def rename(id,data):
 item=repo.get('datasets',id);item['name']=data.name;repo.put('datasets',item);return summary(item)
def parse_value(text):
 text=(text or '').strip()
 if text.lower() in ('','na','null'):return None
 value=float(text)
 if not math.isfinite(value) or abs(value)>1000000:raise ValueError()
 return value

def create(data):
 reader=csv.DictReader(io.StringIO(data.csv_text.lstrip('\ufeff')))
 if not {'station','time_hour','value'}.issubset(reader.fieldnames or []):raise ValueError('CSV需要station,time_hour,value；空值用空字段/NA/null，truth为可选模拟参考列')
 rows=[];last={}
 for n,r in enumerate(reader,2):
  if n>MAX_ROWS+1:raise ValueError('最多5000条观测')
  try:
   if any(r.get(k) is None for k in ('station','time_hour','value')):raise ValueError()
   station=r['station'].strip();time=float(r['time_hour']);value=parse_value(r['value']);truth=parse_value(r.get('truth'))
   if not 1<=len(station)<=30 or not math.isfinite(time) or not 0<=time<=10000000 or station in last and time-last[station]<MIN_TIME_STEP_HOURS:raise ValueError()
  except (ValueError,TypeError):raise ValueError(f'第{n}行站点/时间/数值无效；每站时间须严格递增唯一且步长至少1e-6小时')
  last[station]=time;rows.append({'station':station,'time_hour':time,'value':value,'truth':truth})
 if len(rows)<3 or len(last)>MAX_STATIONS:raise ValueError('至少3条观测且最多8个站点')
 item=ObservationDataset(new_id('ds'),data.name,data.source,rows,now());repo.put('datasets',item);return summary(asdict(item))
