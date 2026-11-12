import hashlib,json
from src.services.reconstruction import reconstruct,evaluate_mask

def analyze(rows,mask,study):
 station=[r for r in rows if r['station']==mask['station']]
 if len(station)<3:raise ValueError('测站至少3条观测')
 times=[r['time_hour'] for r in station];values=[r['value'] for r in station]
 production=reconstruct(times,values,study)
 for original,p in zip(station,production['series']):
  p.update(original_value=original['value'],is_gap=original['value'] is None,rts_output=original['value'] if original['value'] is not None else p['rts_mean'],pchip_output=original['value'] if original['value'] is not None else p['pchip'])
 validation=evaluate_mask(station,mask,study)
 return {'station':mask['station'],'point_count':len(station),'observed_count':sum(v is not None for v in values),'missing_count':sum(v is None for v in values),'pchip_unfilled_gaps':sum(p['is_gap'] and p['pchip_output'] is None for p in production['series']),'production':production,'validation':validation,'mask':mask,'study':study,'checksum':hashlib.sha256(json.dumps({'rows':rows,'mask':mask,'study':study},sort_keys=True).encode()).hexdigest(),'limitations':['局部水平x_t=x_(t-1)+噪声，过程方差q×Δt（小时）；q/r及初始方差固定配置，不从遮挡真值估计','RTS为离线重建，使用未来已观测值；自动初值仅取该次训练剩余首个观测，验证重新初始化，不称在线预测','生产重建使用原始已观测值；验证另跑遮挡序列，两次状态不复用；truth参考列从不进入算法或分母','输出仅补原始缺口，已有观测原样保留；PCHIP需至少2已知点且仅在两端之间插值，边缘不外推留空','状态区间基于P，遮挡带噪观测覆盖基于P+R，二者口径分开','两方法MAE只在共有可估内点比较，同时公开各自覆盖数量/误差；原本缺失不当0、不进验证分母','置信区间依赖局部水平与噪声假设；长缺口可能过平滑，模拟读数不代替环境质控结论']}
