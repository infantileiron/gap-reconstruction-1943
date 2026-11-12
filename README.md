# 芦浦环境 · 测站缺测插补复核

为芦浦环境12人观测组保留原始缺失，用局部水平Kalman/RTS离线重建与PCHIP内点插值复核缺口，并用独立连续遮挡比较误差。

## 场景与六实体

上游 `station_gaps_202611.csv` 为3测站、480小时的1440条模拟观测。团队原来跨列手填，长缺口容易过平滑、边缘外推未标、验证时不慎用到被遮挡真值。本工程替代原始核查、遮挡锁定、固定参数重建、误差复核与归档，下游观测组据此安排实际质控讨论。

ObservationDataset原始观测、GapMask连续验证掩码、ReconstructionStudy参数方案、ReconstructionRun运行、GapReview复核、Report报告，全部贯穿存储/API/界面。六页：缺测档案、原始观测、连续遮挡、重建参数、插补与验证、缺口复核。总览和结果共用GapChart与GapSummary。另有BatchReview离线批量复核实体（第7页），供观测组每晚对多测站多方案一次性复核，不改变上述单次复核口径。

## 快速启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

前端 http://localhost:18228 ，API http://localhost:19228/docs ，PostgreSQL端口17728。恰好frontend/backend/worker/db/redis五服务，全健康检查；数据库、Redis与共享产物用命名卷。清理测试数据：`docker compose down -v --remove-orphans`。

## 离线批量复核（夜间多方案）

Web入口在第7页「批量复核」，勾选多个重建方案建批；离线/无Redis环境用CLI（容器内执行，自动强制inline本进程运行，不依赖队列）：

```sh
# 复核指定方案或全部方案
docker compose exec -T backend python -m scripts.batch_review_cli --studies study-a,study-b --name "11日夜批"
docker compose exec -T backend python -m scripts.batch_review_cli --all
# 中断后续跑：已完成且输入未变的项跳过，不重复计算；有失败项退出码为1便于脚本发现
docker compose exec -T backend python -m scripts.batch_review_cli --batch batch-xxxx --resume
```

逐项隔离try/except：单个坏方案只在该项记录失败原因，不拖垮其他方案，批次状态在全部成功/部分失败/全部失败间区分。每项独立保留原始缺口补值（RTS/PCHIP）、独立遮挡重算的逐点误差与覆盖、边缘不可估清单；全部复用单次复核`analyze`同一入口，遮挡序列另建训练数组、重新初始化，口径与单次完全一致（有测试核对全部metrics与checksum）。

输入指纹（数据集行+掩码+参数的SHA256）随项落盘：续跑或重跑时指纹一致才跳过，数据或参数变更则把旧指纹留痕（previous_fingerprint）并拒绝沿用、强制重算；批次整体已完成时也会先做指纹预检。每算完一项立即落盘，中断不丢已完成项。汇总按有效遮挡点（掩码目标原本有值，analyze已保证）等权加权，原始缺失不进入分母；PCHIP边缘不可估单列且不进入PCHIP分母，RTS分母仍为全部有效遮挡点。批次JSON产物写入共享卷`ARTIFACT_DIR/{batch_id}.batch.json`。

| 账号 | 角色 | 权限 |
|---|---|---|
| admin@lupu.test | admin / 缺测复核工程师 | 六实体、批准/退回、审计 |
| analyst@lupu.test | analyst / 测站数据分析员 | 导入、遮挡、方案、运行、提审、生成报告 |
| viewer@lupu.test | viewer / 环境观察员 | 六实体只读、下载已批准报告 |

统一演示密码 `Gap2026!`。PBKDF2、JWT HS256、actor审计、全局错误恢复、10任务队列配额；匿名401、越权403、重复审批409。JWT_SECRET可配置。

## 一天的工作剧本

1. 09:00 核查station_gaps_202611.csv，3站各480时点，值为空表示缺失，0仍是有效观测。
2. 09:05 上传文件，保留文件名；检查每站时间严格递增唯一，单位小时。
3. 09:10 锁定LP-01第100—111小时的12个原本有值目标作连续遮挡，不把原始缺失纳入验证分母。
4. 09:15 固定q=0.03读数²/h、r=0.09读数²与P0=10000；空初始均值表示本次训练剩余首观测。
5. 09:20 Redis排队，独立Python worker分别运行生产重建和遮挡重算，落PostgreSQL与共享结果JSON。
6. 09:25 对照短/长/首尾缺口，PCHIP边缘留空，RTS仅称离线重建，原始观测不覆盖。
7. 09:30 查看共有内点MAE、各方法覆盖数量，以及基于P+R的有噪观测区间覆盖；状态区间P单独展示。
8. 09:40 提交复核，工程师批准后生成报告，观察员下载完整原始/补值/方差/遮挡记录CSV。

## 输入、缺失与掩码

CSV必需station,time_hour,value；可选truth为模拟完整带噪观测参考。空字段、NA、null为缺失；NaN/Inf拒绝，不把缺失当0。每站时间严格递增唯一、至少约1e-6小时步长，允许不规则时间；时间范围[0,1e7]小时，读数绝对值≤1e6，最多5000条/8站。短行、重复/倒序时间明确422。

truth参考列保留供模拟数据审阅，但不进入任何训练、初始化、参数估计或验证分母。验证真值只取掩码目标原本有值的value。连续掩码端点须匹配实际时刻、包含2—48条，区间内任何原始缺失都会拒绝。研究数据与掩码数据必须一致。

## Kalman与RTS离线状态

局部水平模型x_t=x_(t−1)+η，过程方差q×Δt（小时），观测y_t=x_t+ε，观测噪声方差r。q/r固定配置、有限正值且≤100；初始方差(0,1e8]，可指定固定初始均值。自动均值只取本次训练剩余的首个有值观测，缺训练观测明确失败。

滤波预测P⁻_t=P_(t−1)+qΔt，K=P⁻/(P⁻+r)，更新m=m⁻+K(y−m⁻)、P=rP⁻/(P⁻+r)；缺失时仅预测。RTS向后增益C=P_f/P⁻_(t+1)，更新平滑均值和方差。方差用等价稳定表达P_s=P_f(1−C)+C²P_s,next，避免相减数值不稳定；平滑方差非负且不大于对应滤波方差。

RTS使用未来已观测值，自动初值也可能位于序列起点之后，因此本产品始终称离线重建，滤波中间量不作为在线预测承诺。参数不根据被遮挡真值自动拟合。区间依赖局部水平/高斯噪声等假设，不代表质控保证。

## PCHIP与边缘

使用分段三次Hermite形状保持插值。内点导数为同号相邻割线的加权调和均值；变号/零割线导数置0，端点采用限制导数。至少2个已知点，仅在最早与最晚已知点之间估计；边缘不外推，无法估计返回null而不是0。只有1个已知点时也不假装能补其他时刻。

## 生产与验证分开

生产重建使用全部原始已观测值，输出仅填原始缺口；已有观测的rts_output/pchip_output都原样保留。RTS状态均值是单独字段，不拿平滑值覆盖实测值。

遮挡验证另建训练数组，把目标value设为null，重新初始化并重跑两方法，不复用生产状态/初值。预测完成后才读取原始目标值计算误差。修改被遮挡值不会改变验证预测/初值/方差；只会改变评估真值与误差。

潜在状态方差P与有噪观测方差P+r分别保存。主图阴影为状态95%区间m±1.96√P；遮挡图和覆盖统计使用有噪观测区间m±1.96√(P+r)。不能用较窄的P区间核验有噪观测覆盖。

两方法公平MAE只在双方均可估的共有内点上计算；同时公开target_count、各自可估数量和独立MAE。PCHIP边缘目标不可估时common_count可为0，共有MAE返回null，RTS自身计数和误差另列。原始未知值从不进验证分母。

## 批量复核口径

批量复核不引入第二套算法：每个方案都调用与单次运行完全相同的`statistics.analyze`，生产重建与遮挡验证仍分两次独立重算。批次只在其上做三件事——逐项留痕（补值、逐点遮挡误差、失败原因、输入指纹）、断点续跑（每项算完即落盘，未变更的完成项跳过，变更项旧指纹留痕后重算）、加权汇总（有效遮挡点等权，原始缺失不进分母，边缘不可估单列）。失败项不参与汇总分母，也不影响其他项；引用的方案/掩码/数据被删时该项记为失败并保留原因。CLI在`scripts/batch_review_cli.py`，服务端到端核对在`tests/test_batch_review.py`（纯标准库可跑，不依赖外部服务）。

## 技术与结构

| 层 | 技术 |
|---|---|
| 前端 | React18 / TypeScript5.7 / Vite6 / Nginx1.28 |
| 后端 | Python3.12 / FastAPI / psycopg3 |
| 算法 | Python math/bisect，Kalman/RTS和PCHIP自实现 |
| 异步与持久化 | Redis7.4 / 独立worker / PostgreSQL16 |

78职责源文件。后端src/{routes,controllers,services,models,schemas,middlewares,utils,constants,config}，前端src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。TEXT主键+JSON文本业务表，DDL在backend/migrations/001_initial.sql；advisory lock保护首次并发建表。

枚举：后端src/constants/enums.py角色/运行/复核/批次状态及src/constants/domain.py配额/区间常数；前端src/constants/enums.ts。环境DATABASE_URL、REDIS_URL、JWT_SECRET、SEED_DEMO、TASK_MODE、ARTIFACT_DIR及端口/口令见.env.example。

Seed固定2309，480小时×3站=1440条，LP-01有41个短/长/边缘缺口；其他站另有缺口。完整带噪模拟参考truth保留但不入算法。SEED_DEMO=true自动seed，自然键insert-only，保留手工修改、重复不新增，失败记录日志。每次研究选一个掩码所属测站运行480时点。

前端npm ci沿用已测配套锁，仅改根包名。开发后端配置PG/Redis并安装requirements，运行uvicorn src.main:app --reload；前端npm ci && npm run dev，通过Nginx或/api代理访问。Nginx上限6MiB，前端文件1.8MB，API文本字段1.8M字符。

## 已知边界

模拟读数不代替环境质控；局部水平在长缺口/周期变化下可能过平滑，固定q/r需要业务核查。PCHIP无概率区间，不输出虚构覆盖率。没有参数自动估计或真实在线预测。Redis出队后强杀无自动重投，需要重提；JSON载荷无多人乐观锁和迁移回滚。默认账号仅本地演示。

真实容器、HTTP、独立手算oracle、浏览器与截图在批次test-artifacts/gb-2309，源码不含测试截图/日志/报告。

## License

MIT，见LICENSE。
