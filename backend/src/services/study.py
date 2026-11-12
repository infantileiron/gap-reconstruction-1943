from src.models.entities import ReconstructionStudy
from src.utils import repository as repo
from src.utils.identity import new_id,now

def list_studies():return repo.all_rows('studies')
def create(data):
 repo.get('datasets',data.dataset_id);mask=repo.get('masks',data.mask_id)
 if mask['dataset_id']!=data.dataset_id:raise ValueError('掩码与研究数据集必须一致')
 return repo.put('studies',ReconstructionStudy(new_id('study'),data.name,data.dataset_id,data.mask_id,data.q_per_hour,data.observation_r,data.initial_variance,data.initial_level,now()))
