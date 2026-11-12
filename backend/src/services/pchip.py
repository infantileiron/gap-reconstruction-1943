import bisect,math

def sign(v):return 1 if v>0 else -1 if v<0 else 0
def endpoint(h0,h1,d0,d1):
 derivative=((2*h0+h1)*d0-h0*d1)/(h0+h1)
 if sign(derivative)!=sign(d0):return 0.
 if sign(d0)!=sign(d1) and abs(derivative)>abs(3*d0):return 3*d0
 return derivative

def pchip_values(times,values,queries):
 if len(times)!=len(values) or any(not math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('PCHIP时间长度/顺序无效')
 if any(not math.isfinite(query) for query in queries):raise ValueError('插值查询时间非有限')
 known=[(t,v) for t,v in zip(times,values) if v is not None]
 if any(not math.isfinite(t) or not math.isfinite(v) for t,v in known) or any(b[0]<=a[0] for a,b in zip(known,known[1:])):raise ValueError('PCHIP已知点时间/值无效或不唯一')
 if len(known)<2:return [next((v for t,v in known if t==query),None) for query in queries]
 x=[p[0] for p in known];y=[p[1] for p in known];h=[b-a for a,b in zip(x,x[1:])];delta=[(b-a)/step for a,b,step in zip(y,y[1:],h)];n=len(x)
 if n==2:d=[delta[0],delta[0]]
 else:
  d=[endpoint(h[0],h[1],delta[0],delta[1])]
  for i in range(1,n-1):
   if delta[i-1]==0 or delta[i]==0 or sign(delta[i-1])!=sign(delta[i]):d.append(0.)
   else:
    w1=2*h[i]+h[i-1];w2=h[i]+2*h[i-1];d.append((w1+w2)/(w1/delta[i-1]+w2/delta[i]))
  d.append(endpoint(h[-1],h[-2],delta[-1],delta[-2]))
 result=[]
 for query in queries:
  if not math.isfinite(query):raise ValueError('插值查询时间非有限')
  if query<x[0] or query>x[-1]:result.append(None);continue
  i=min(n-2,bisect.bisect_right(x,query)-1);u=(query-x[i])/h[i]
  result.append((2*u**3-3*u**2+1)*y[i]+(u**3-2*u**2+u)*h[i]*d[i]+(-2*u**3+3*u**2)*y[i+1]+(u**3-u**2)*h[i]*d[i+1])
 return result
