from dataclasses import dataclass,field
from typing import Any
@dataclass
class ObservationDataset:
 id:str
 name:str
 source:str
 rows:list[dict]
 created_at:str=''
@dataclass
class GapMask:
 id:str
 name:str
 dataset_id:str
 station:str
 start_hour:float
 end_hour:float
 target_times:list[float]
 created_at:str=''
@dataclass
class ReconstructionStudy:
 id:str
 name:str
 dataset_id:str
 mask_id:str
 q_per_hour:float=.03
 observation_r:float=.09
 initial_variance:float=10000
 initial_level:float|None=None
 created_at:str=''
@dataclass
class ReconstructionRun:
 id:str
 study_id:str
 status:str='queued'
 result:dict[str,Any]=field(default_factory=dict)
 error:str=''
 created_at:str=''
@dataclass
class GapReview:
 id:str
 run_id:str
 comment:str
 status:str='pending'
 reviewer:str=''
 created_at:str=''
@dataclass
class BatchReview:
 id:str
 name:str
 study_ids:list[str]
 status:str='queued'
 items:list[dict]=field(default_factory=list)
 summary:dict[str,Any]=field(default_factory=dict)
 error:str=''
 created_at:str=''
 updated_at:str=''
@dataclass
class Report:
 id:str
 run_id:str
 review_id:str
 title:str
 created_at:str=''
