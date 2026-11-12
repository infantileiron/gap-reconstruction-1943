export const roleLabels:Record<string,string>={admin:'缺测复核工程师',analyst:'测站数据分析员',viewer:'环境观察员'};
export const runLabels:Record<string,string>={queued:'排队中',running:'重建中',completed:'已完成',failed:'失败',pending:'待复核',approved:'已通过',rejected:'已退回',partial:'部分失败',stale:'输入已变更'};
export const batchLabels:Record<string,string>={queued:'排队中',running:'复核中',completed:'已完成',partial:'部分失败',failed:'全部失败',pending:'待处理',stale:'输入已变更'};
export const methodLabels={rts:'RTS离线重建',pchip:'PCHIP内点插值'};
