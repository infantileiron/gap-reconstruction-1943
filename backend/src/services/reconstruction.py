import math
from src.services.kalman import kalman_rts
from src.services.pchip import pchip_values
from src.constants.domain import INTERVAL_Z

def reconstruct(times,values,study):
 k=kalman_rts(times,values,study['q_per_hour'],study['observation_r'],study['initial_variance'],study['initial_level']);p=pchip_values(times,values,times)
 rows=[]
 for i,t in enumerate(times):
  state_sd=math.sqrt(k['state_variance'][i]);observation_sd=math.sqrt(k['observation_variance'][i]);mean=k['smoothed_mean'][i]
  rows.append({'time_hour':t,'training_value':values[i],'filtered_mean':k['filtered_mean'][i],'filtered_variance':k['filtered_variance'][i],'rts_mean':mean,'state_variance':k['state_variance'][i],'observation_variance':k['observation_variance'][i],'state_low':mean-INTERVAL_Z*state_sd,'state_high':mean+INTERVAL_Z*state_sd,'observation_low':mean-INTERVAL_Z*observation_sd,'observation_high':mean+INTERVAL_Z*observation_sd,'pchip':p[i]})
 return {'series':rows,'initial_level_used':k['initial_level_used']}

def evaluate_mask(rows,mask,study):
 times=[r['time_hour'] for r in rows];target=set(mask['target_times']);truth={r['time_hour']:r['value'] for r in rows if r['time_hour'] in target}
 if len(truth)!=len(target) or any(v is None for v in truth.values()):raise ValueError('验证掩码含原本未知或不存在的值')
 training=[None if r['time_hour'] in target else r['value'] for r in rows]
 reconstructed=reconstruct(times,training,study);evaluated=[];series=[]
 for p in reconstructed['series']:
  is_target=p['time_hour'] in target;row={**p,'is_target':is_target,'validation_truth':truth[p['time_hour']] if is_target else None};series.append(row)
  if is_target:evaluated.append(row)
 common=[p for p in evaluated if p['pchip'] is not None];rts_errors=[abs(p['rts_mean']-p['validation_truth']) for p in evaluated];pchip_errors=[abs(p['pchip']-p['validation_truth']) for p in common]
 mean=lambda values:sum(values)/len(values) if values else None
 coverage=sum(p['observation_low']<=p['validation_truth']<=p['observation_high'] for p in evaluated)
 return {**reconstructed,'series':series,'targets':evaluated,'metrics':{'target_count':len(evaluated),'rts_available_count':len(evaluated),'pchip_available_count':len(common),'common_count':len(common),'rts_mae_common':mean([abs(p['rts_mean']-p['validation_truth']) for p in common]),'pchip_mae_common':mean(pchip_errors),'rts_mae_all':mean(rts_errors),'pchip_mae_all':mean(pchip_errors),'rts_observation_interval_covered':coverage,'rts_observation_interval_count':len(evaluated),'rts_observation_interval_coverage':coverage/len(evaluated) if evaluated else None}}
