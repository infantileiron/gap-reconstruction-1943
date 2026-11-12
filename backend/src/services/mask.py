from src.models.entities import GapMask
from src.utils import repository as repo
from src.utils.identity import new_id,now
from src.constants.domain import MAX_MASK_POINTS

def list_masks():return repo.all_rows('masks')
def create(data):
 dataset=repo.get('datasets',data.dataset_id)
 if data.start_hour>=data.end_hour:raise ValueError('遮挡起点必须小于终点')
 selected=[r for r in dataset['rows'] if r['station']==data.station and data.start_hour<=r['time_hour']<=data.end_hour]
 if not 2<=len(selected)<=MAX_MASK_POINTS or selected[0]['time_hour']!=data.start_hour or selected[-1]['time_hour']!=data.end_hour:raise ValueError('连续遮挡须匹配实际时间端点且包含2—48个时点')
 if any(r['value'] is None for r in selected):raise ValueError('验证遮挡目标必须原本有观测值，不能把未知值当真值')
 return repo.put('masks',GapMask(new_id('mask'),data.name,data.dataset_id,data.station,data.start_hour,data.end_hour,[r['time_hour'] for r in selected],now()))
