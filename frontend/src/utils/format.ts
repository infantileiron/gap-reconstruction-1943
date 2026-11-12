export const decimal=(v:number|null|undefined,d=4)=>v==null?'不可估计':v.toFixed(d);export const percent=(v:number|null)=>v===null?'不可估计':(v*100).toFixed(1)+'%';
