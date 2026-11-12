from pydantic import BaseModel,Field,ConfigDict
from typing import Literal
class InputModel(BaseModel):
 model_config=ConfigDict(allow_inf_nan=False)
class LoginInput(InputModel):
 email:str
 password:str
class DatasetInput(InputModel):
 name:str=Field(min_length=2,max_length=100)
 source:str=Field(default='station_gaps_202611.csv',max_length=100)
 csv_text:str=Field(min_length=20,max_length=1800000)
class RenameDataset(InputModel):
 name:str=Field(min_length=2,max_length=100)
class MaskInput(InputModel):
 name:str=Field(min_length=2,max_length=100)
 dataset_id:str
 station:str=Field(min_length=1,max_length=30)
 start_hour:float=Field(default=100,ge=0,le=10000000)
 end_hour:float=Field(default=111,ge=0,le=10000000)
class ReconstructionStudyInput(InputModel):
 name:str=Field(min_length=2,max_length=100)
 dataset_id:str
 mask_id:str
 q_per_hour:float=Field(default=.03,gt=0,le=100)
 observation_r:float=Field(default=.09,gt=0,le=100)
 initial_variance:float=Field(default=10000,gt=0,le=100000000)
 initial_level:float|None=Field(default=None,ge=-1000000,le=1000000)
class RunInput(InputModel):
 study_id:str
class ReviewInput(InputModel):
 run_id:str
 comment:str=Field(min_length=5,max_length=2000)
class DecisionInput(InputModel):
 status:Literal['approved','rejected']
 comment:str=Field(min_length=5,max_length=2000)
class ReportInput(InputModel):
 run_id:str
 review_id:str
 title:str=Field(min_length=2,max_length=100)
