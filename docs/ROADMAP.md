# Instrument Capture Studio Roadmap

## 目标

第一版完成 DSO-X 3034A + FSW 商业化联合采集工具。

第一版固定为 8 个 Phase。

Phase 8 完成后发布 v1.0.0。

---

## Phase 1 - 项目基础架构

目标：

- 建立 Python 项目结构
- 明确仓库职责边界
- 建立核心数据模型
- 建立 Adapter 接口
- 建立 Workflow 接口
- 建立基础异常体系
- 建立测试框架

结果：

项目可以运行基础测试，但暂不连接真实仪表。

---

## Phase 2 - DSO-X 3034A 接入

目标：

- 接入 DSO-X 3034A 底层驱动
- 仪表连接
- 身份识别
- 状态查询
- DELAY 配置与采集
- CYCLES 配置与采集
- 波形读取
- 基础错误处理

结果：

可以独立完成 DSO-X 3034A 真机采集。

---

## Phase 3 - FSW 接入

目标：

- 接入 FSW 底层驱动
- 仪表连接
- 身份识别
- 状态查询
- 频谱配置
- 单次频谱采集
- Trace 数据读取
- 基础错误处理

结果：

可以独立完成 FSW 真机采集。

---

## Phase 4 - 联合采集 Workflow

状态：

**COMPLETE**

已完成：

- 统一 Capture Job
- FSW Spectrum
- DSO-X DELAY
- DSO-X CYCLE_COUNT
- DSO-X Waveform
- Save Result Step
- Step 状态
- Job 状态
- 超时
- 运行中取消
- 重试
- 失败处理
- 无 GUI CLI 联合采集入口
- FSW timeout 真机验证
- FSW runtime cancel 真机验证
- DSO-X 3034A 真机参与联合采集验证
- FSW + DSO-X 双仪表完整联合采集验证

2026-08-26：通过 Windows GUI 使用默认界面配置完成 FSW + DSO-X 双仪表完整联合采集。

目标：

建立统一 Capture Job。

第一版支持：

FSW Spectrum
↓
DSO-X DELAY
↓
DSO-X CYCLES
↓
DSO-X Waveform
↓
Save Result

同时支持：

- Step 状态
- 超时
- 取消
- 重试
- 失败处理
- Job 状态

结果：

可以无 GUI 或通过 GUI 完成一次完整联合采集。

---

## Phase 5 - 数据管理

状态：

**COMPLETE**

已完成：

- CSV 保存
- NPZ 保存
- metadata.json 元数据保存
- job.json Job Manifest
- 文件命名规则
- 标准采集目录结构
- Job ID
- 仪表身份信息记录
- 仪表配置参数快照
- Job / Step 时间记录
- Job / Step 错误记录
- 成功 / 失败 / 取消状态持久化
- 连接阶段失败记录
- Spectrum / Waveform 数据重新加载
- CaptureContext 离线恢复
- CLI 真实磁盘保存入口
- 同一 Job 跨午夜保持单一目录
- 运行时 data 目录 Git 忽略规则
- 双仪表真机完整数据目录验证

数据目录：

YYYY-MM-DD/
└── job_id/
    ├── job.json
    ├── metadata.json
    ├── spectrum.csv
    ├── spectrum.npz
    ├── waveform.csv
    └── waveform.npz

结果：

一次采集可以产生完整、可追踪、可重新加载的数据目录。

2026-08-26：GUI 真机联合采集确认生成全部 6 个标准文件：
`job.json`、`metadata.json`、`spectrum.csv`、`spectrum.npz`、`waveform.csv`、`waveform.npz`。

---

## Phase 6 - 商业桌面 UI

状态：

**BASELINE COMPLETE**

已完成：

- Windows PySide6 GUI
- DSO-X 连接状态与连接测试
- FSW 连接状态与连接测试
- 仪表地址配置
- FSW / DSO-X 参数配置
- 开始采集
- 停止采集
- 实时 Capture Step 进度
- Job 状态
- 日志窗口
- 数据浏览
- Windows EXE 启动验证
- FSW 真机连接测试
- DSO-X 真机连接测试
- GUI 双仪表完整联合采集验证
- 完整数据目录落盘验证

2026-08-26：Windows GUI 使用默认配置完成真实 FSW + DSO-X 联合采集，数据目录完整生成。

结果：

用户不需要操作命令行即可完成仪表连接测试、联合采集和结果保存。

界面细节优化、长期运行能力、批量扫频采集、模板、可视化和报告进入 Phase 7。

---

## Phase 7 - 稳定性与产品能力

状态：

**IN PROGRESS**

### Phase 7A - 参数持久化

状态：

**COMPLETE**

已完成：

- 自动保存上一次 FSW VISA 地址
- 自动保存上一次 DSO-X VISA 地址
- 自动保存 FSW Center / Span / RBW / VBW / Trigger / Timeout
- 自动保存 DSO-X DELAY / CYCLE_COUNT / Waveform Channel 参数
- 自动保存数据输出目录
- 自动保存批量扫频参数
- 下次启动 GUI 自动恢复上一次参数

原则：常用实验参数不要求用户每次重新填写。

### Phase 7B - 断线检测与自动恢复

状态：

**SOFTWARE COMPLETE / HARDWARE ACCEPTANCE IN PHASE 8**

已完成软件能力：

- 连接异常与通信异常分类
- Capture Job 运行中通信故障检测
- 自动重新创建全新的 VISA / Driver / Adapter 会话
- 默认最多 4 次 Capture 尝试
- 自动重连等待 2 秒，等待期间可立即响应用户停止
- 重试使用新的 Job ID，保留前一次失败的 job.json，不覆盖故障证据
- GUI 显示 `RECONNECTING` 状态和重连次数
- 正常 Trigger / Measurement timeout 不自动重试，避免把测量条件问题误判为掉线
- 已有 FSW bounded timeout、运行中取消和安全 ABORt 能力继续复用
- Fault Injection 自动验证通信故障后释放旧会话、重新连接并重试

当前自动恢复策略：

连接/通信异常
↓
当前 Job 正常结束并记录失败
↓
释放旧 VISA 会话
↓
等待 2 秒
↓
重新创建两台仪表 Adapter
↓
使用新 Job ID 从完整 Capture Workflow 重新开始
↓
最多 4 次

验证策略：

- 开发阶段使用可重复的 Fault Injection / Fake Adapter 自动测试连接中断、通信中断和重连逻辑
- Windows 防火墙按仪表 IP 临时阻断可作为有条件的网络故障模拟手段
- FSW / DSO-X 实际拔线、插回、最大重试失败等真机异常验收统一纳入 Phase 8

### Phase 7C - 频率循环 / 批量联合采集

状态：

**BASELINE COMPLETE + LARGE REAL-HARDWARE RUN PASSED**

用户可配置：

- 起始中心频率，例如 700 MHz
- 结束中心频率，例如 800 MHz
- 频率步长，例如 5 MHz
- Span，允许 0 或仪表支持的任意有效值
- 每个中心频率的联合采集次数

已完成：

- `FrequencySweepPlan` 软件模型
- 起始 / 结束 / 步长 / Span / 每频点采集次数验证
- Batch Capture Runner
- Batch 内保持 FSW + DSO-X 长连接
- FSW 当前中心频率动态切换
- 每频点完整执行 Spectrum + DELAY + CYCLE_COUNT + Waveform
- 每次采集保持独立 Job ID 和 6 个标准数据文件
- Batch ID / `batch.json`
- Batch 进度、当前频率、当前次数、总完成数
- 批量模式中途安全停止
- 批量运行中的连接/通信异常自动恢复
- GUI “单次采集 / 频率循环采集”模式
- GUI 起始频率 / 结束频率 / 步长 / Span / 每频点次数
- 批量参数自动保存 / 恢复

2026-08-26 真机长时间批量验证：

- 700 MHz → 800 MHz
- 步长 5 MHz
- 21 个频点
- 每频点 100 次完整联合采集
- 总计 2100 次联合采集完成

该验证说明 Batch 长连接、动态频率切换、大规模 Job 数据保存和 GUI 长时间运行链路已具备实际可用基础。

### Phase 7D - 产品增强

当前已完成：

- 命名实验配置模板保存 / 加载 / 删除
- 模板保存 VISA、FSW、DSO-X、扫频和输出目录参数
- 针对数千 Job 数据集的 Batch / Job 摘要浏览模型
- GUI 只展示最近 Batch / Job，避免一次性渲染数万个文件项
- 双击 Job 打开数据目录
- 双击 `batch.json` / `job.json` / `metadata.json` 查看结构化详情
- 双击 `spectrum.npz` 查看频谱曲线
- 双击 `waveform.npz` 查看时域波形
- 大数组曲线预览自动抽样，避免 GUI 因数万点绘图卡顿
- 桌面会话日志持久化到用户目录，适合长时间运行问题追踪
- Batch HTML 报告生成
- 完整 Batch Job 明细导出为 `jobs.csv`
- 每个频点自动选择一个成功 Job 生成代表性 Spectrum / Waveform SVG 曲线
- GUI 选择 Batch 后一键生成并打开 HTML 报告

后续目标：

- 仪表忙处理
- 更完整的异常恢复
- 普通连续采集模式
- 全量批量转图模式
- PDF 报告
- UI 细节与产品体验优化

结果：

从“能用”进入“可长期运行”，并支持真实批量实验数据采集流程。

---

## Phase 8 - 验收与商业发布

目标：

- 完整实机测试
- 长时间稳定性测试
- 断网测试
- 仪表掉线测试
- 异常场景测试
- Windows 打包
- 配置目录整理
- 日志目录整理
- 用户文档
- 部署文档
- Release 构建

最终发布：

v1.0.0

---

## 第一版范围冻结

v1.0.0 核心仪表：

- Keysight DSO-X 3034A
- Rohde & Schwarz FSW

其他型号不作为 v1.0.0 必须完成项。

新增仪表型号和新增业务需求原则上进入后续版本。
