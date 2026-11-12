import math

def kalman_rts(times,values,q,r,initial_variance=10000,initial_level=None):
 if len(times)!=len(values) or not times:raise ValueError('滤波时间/序列长度无效')
 if any(not math.isfinite(x) for x in (q,r,initial_variance)) or min(q,r,initial_variance)<=0:raise ValueError('q/r/初始方差必须是正有限值')
 if any(not math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('时间必须严格递增唯一')
 known=[v for v in values if v is not None]
 if not known:raise ValueError('没有训练观测，不能初始化离线重建')
 if any(not math.isfinite(v) for v in known) or initial_level is not None and not math.isfinite(initial_level):raise ValueError('观测或初值非有限')
 initial=known[0] if initial_level is None else initial_level;mp=[];pp=[];mf=[];pf=[]
 for i,(t,y) in enumerate(zip(times,values)):
  mean=initial if i==0 else mf[-1];variance=initial_variance if i==0 else pf[-1]+q*(t-times[i-1])
  mp.append(mean);pp.append(variance)
  if y is None:mf.append(mean);pf.append(variance)
  else:
   gain=variance/(variance+r);mf.append(mean+gain*(y-mean));pf.append(r*variance/(variance+r))
 ms=list(mf);ps=list(pf)
 for i in range(len(times)-2,-1,-1):
  gain=pf[i]/pp[i+1];ms[i]=mf[i]+gain*(ms[i+1]-mp[i+1])
  # Algebraically equivalent RTS variance, with a nonnegative stable decomposition.
  ps[i]=min(pf[i],max(0.,pf[i]*(1-gain)+gain*gain*ps[i+1]))
 return {'filtered_mean':mf,'filtered_variance':pf,'smoothed_mean':ms,'state_variance':ps,'observation_variance':[p+r for p in ps],'initial_level_used':initial,'initial_variance':initial_variance}
