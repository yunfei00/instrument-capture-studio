# Instrument Capture Studio Roadmap

## 目标

第一版完成 DSO-X 3034A + FSW 商业化联合采集工具。

第一版固定为 8 个 Phase，Phase 8 完成后发布 v1.0.0。

---

## Phase 1 - 项目基础架构

状态：**COMPLETE**

已完成 Python 项目结构、仓库职责边界、核心数据模型、Adapter / Workflow 接口、基础异常体系和测试框架。

---

## Phase 2 - DSO-X 3034A 接入

状态：**COMPLETE**

已完成 DSO-X 3034A 驱动接入、连接、身份识别、状态查询、DELAY、CYCLE_COUNT、Waveform 与基础错误处理，并已参与真实双仪表联合采集。

---

## Phase 3 - FSW 接入

状态：**COMPLETE**

已完成 FSW 驱动接入、连接、身份识别、状态查询、频谱配置、单次频谱采集、Trace 读取、bounded timeout、运行中取消和真机资格验证。

---

## Phase 4 - 联合采集 Workflow

状态：**COMPLETE**

已完成统一 Capture Job、Step / Job 状态、超时、协作式取消、重试与失败处理、CLI / GUI 联合采集入口，以及 DSO-X + FSW 双仪表真机联合采集验证。

2026-08-26：Windows GUI 使用默认配置完成真实 FSW + DSO-X 完整联合采集。

Phase 4 的旧联合采集顺序只作为工程基线；Phase 8A 已按真实 EXT ARM → DSO-X DELAY 采集触发 → EXT Read → DSO-X CYCLE 第二次采集 → IMM 的业务顺序完成正式 Recipe 对齐。

---

## Phase 5 - 数据管理

状态：**COMPLETE（工程基线）**

已完成 CSV / NPZ、metadata.json、job.json、标准目录、Job ID、仪表身份与配置快照、错误记录、重新加载和跨午夜目录等基础能力。

Phase 5 使用的旧 `spectrum.csv / spectrum.npz` 目录属于开发阶段格式。由于尚未开始正式数据采集，Phase 8A 已直接建立新的正式数据 Schema v1，不兼容旧调试数据格式。

---

## Phase 6 - 商业桌面 UI

状态：**BASELINE COMPLETE / HARDWARE ACCEPTED**

已完成 Windows PySide6 GUI、两台仪表连接测试、VISA 与参数配置、开始 / 停止、实时进度、Job 状态、日志、数据浏览、Windows EXE 启动验证和 GUI 双仪表完整联合采集验证。

---

## Phase 7 - 稳定性与产品能力

状态：**COMPLETE**

### Phase 7A - 参数持久化

状态：**COMPLETE**

已完成 FSW / DSO-X / 输出目录 / 批量参数 / 固定频率连续参数的自动保存与恢复。

### Phase 7B - 断线检测与自动恢复

状态：**SOFTWARE COMPLETE / PHYSICAL CABLE ACCEPTANCE IN PHASE 8**

已完成连接 / 通信异常分类、失败记录、旧会话释放、自动重新建立 VISA 会话、有限次数完整 Job 重试、GUI `RECONNECTING`、Trigger Timeout 与掉线区分以及 Fault Injection 验证。

### Phase 7C - 频率循环 / 批量联合采集

状态：**COMPLETE + LARGE DEBUG HARDWARE RUN PASSED**

已完成 FrequencySweepPlan、Batch Runner、Batch 内长连接、动态中心频率、独立 Job、batch.json、进度、安全停止和批量自动恢复。

2026-08-26 调试稳定性验证：

- 700 MHz → 800 MHz
- 步长 5 MHz
- 21 个频点
- 每频点 100 次
- 总计 2100 次完整联合采集完成

这 2100 次数据仅作为开发阶段稳定性验证，可全部删除，**不属于正式数据集，也不要求数据格式兼容**。

### Phase 7D - 产品增强

状态：**COMPLETE FOR ENGINEERING BASELINE**

已完成命名模板、大规模 Batch / Job 摘要浏览、JSON 查看、Spectrum / Waveform 预览、日志持久化、Batch HTML 报告、jobs.csv、SVG 导出、固定频率连续采集等工程能力。

---

## Phase 8 - 验收与商业发布

状态：**IN PROGRESS**

当前版本：`0.9.0rc1`

### Phase 8A - 正式 Recipe + 正式数据 Schema v1

状态：**COMPLETE**

已完成并真机验收：

- GUI 将“采集内容”和“执行方式”拆成独立维度。
- Recipe A：`EXT联合 + IMM配对样本`。
- Recipe B：`IMM频谱单采`，不要求 DSO-X 在线。
- Recipe C：`DSO-X示波器单采`，不要求 FSW 在线。
- DSO-X Waveform Channel 可选 CH1～CH4，默认 CH1 并自动记忆。
- FSW Driver / Adapter 支持 ARM 与 wait/read 分离。
- 正式 EXT+IMM 流程固定为：FSW EXT ARM → DSO-X DELAY 组独立采集并触发 FSW → FSW EXT wait/read → DSO-X CYCLE 组第二次独立采集 → FSW IMM → 保存。
- DELAY 默认时基 `5e-7 s/div`，CYCLE 默认时基 `1e-4 s/div`，均可在 GUI 配置并记忆。
- 正式数据格式从 Schema v1 起步，不承担旧调试数据兼容。
- 配对 Job 明确保存 `spectrum_ext`、`spectrum_imm`、`waveform_delay`、`waveform_cycle` 四类 CSV/NPZ 数据。
- Data Browser / Trace Viewer / HTML Report / 全量曲线导出 / Phase 8 preflight 已适配正式命名。
- 2026-08-27：真实单次 `EXT联合 + IMM配对样本` 真机采集通过，四类数据文件均正确生成。
- 2026-08-27：`IMM频谱单采 × 1` 真机通过。
- 2026-08-28：`DSO-X示波器单采 × 1` 真机通过；此前 Timeout 最终定位为 USB→TCP 转发工具误把二进制 Waveform 数据做 ASCII 转换，转发链路修复后通过。

正式 Schema v1 至此冻结；后续 Phase 8 不再调整其核心采集语义和文件命名，除非发现阻塞发布的数据一致性缺陷。

### Phase 8B - 暂停与断点续采

状态：**COMPLETE**

已完成并真机验收：

- 批量采集过程中可请求暂停；只在完整逻辑样本边界进入 `PAUSED`。
- 暂停时释放 FSW + DSO-X 会话；继续时重新建立会话。
- 暂停后继续不会重复已成功逻辑样本。
- 主动停止后的 Batch 可继续。
- 程序异常退出留下 `running` Batch 时，可在重新启动后发现并继续。
- 半个逻辑样本不会与新数据拼接；恢复时使用 `-resumeN` 新 Job ID 完整重采该逻辑样本。
- GUI 提供“暂停采集 / 继续采集 / 继续上次任务”。
- 每个正式 Batch 新增独立的冻结参数快照：`<output_root>/batch-configs/<batch_id>.json`。
- 参数快照保存 FSW / DSO-X 完整运行参数、Recipe 和执行方式；重启续采使用原 Batch 快照，不依赖当前 GUI / QSettings 临时值。
- 旧调试 Batch 没有冻结参数快照时不会被误识别为可续采正式任务。
- 2026-08-27：固定频率重复 10 次真机验收通过，完成“暂停 → 继续 → 停止 → 关闭程序 → 重新打开 → 继续上次任务”，最终补齐 10/10。
- 2026-08-27：续采前故意修改 GUI 参数后，程序仍正确恢复原 Batch 的 Channel 与 DELAY/CYCLE 时基，符合冻结参数设计。

### Phase 8C - 节点耗时与性能统计

状态：**SOFTWARE COMPLETE / HARDWARE DATA REVIEW PENDING**

已完成：

- Job `started_at / finished_at / duration_ms`。
- 每个 Workflow Step `started_at / finished_at / duration_ms / state / error`。
- Batch Job 记录 FSW 频率配置耗时。
- 正式配对流程可统计 `fsw_ext_arm`、`dsox_delay_group`、`fsw_ext_read`、`dsox_cycle_group`、`fsw_imm`、`save_result` 和完整 Job。
- Batch 从持久化 Job 数据计算成功样本的 average / P95 / max。
- HTML Batch Report 新增“节点耗时统计”。
- 每份 Batch Report 同时生成 `timing.csv`，方便后续性能分析。
- 失败 / timeout Job 保留原始时间数据用于诊断，但不混入正常性能统计。

待真机数据复核：使用 Phase 8B 已通过的 10 次验收数据检查 timing.csv 和 HTML 统计是否与实际采集时间量级一致。

### Phase 8D - 异常与恢复真机验收

状态：**COMPLETE**

软件与真机验收已完成：

- 采集中关闭 GUI 时不强制销毁 VISA Worker Thread；关闭请求转换为协作式停止，等待当前仪表操作安全结束并释放会话后自动退出。
- 连接测试尚未结束时关闭 GUI，同样等待测试完成后再退出，不使用 `QThread.terminate()`。
- Release Window 继续继承 Phase 8B 的冻结参数与断点续采能力。
- Windows CI smoke test 使用真实 `release_window`。
- FSW 物理网线断开后插回，GUI 进入 `RECONNECTING` 并自动恢复继续采集：PASS。
- DSO-X 当前 USB→TCP Bridge 的 TCP/网线链路断开后恢复，可自动重连并继续采集：PASS。
- 保持断线直到最大尝试次数耗尽，最终明确 `FAILED`，不会无限重试：PASS。
- EXT Trigger Timeout 在 `fsw_ext_read` 正确超时并 `FAILED`，不会误进入 `RECONNECTING`；触发线恢复后下一次单采正常：PASS。
- 采集中直接关闭 GUI，能够安全停止并自动退出；重新打开后可识别未完成任务并继续：PASS。

USB→TCP Bridge 的 USB/转发器侧直接拔除属于桥接层特有故障，本版本列为 OPTIONAL，不阻塞 v1.0.0。

### Phase 8E - Release Candidate

状态：**IN PROGRESS**

下一步完成节点耗时真机数据复核、Release Candidate Windows 构建与真机验收，然后执行最终发布检查。

全部通过后：

- 版本改为 `1.0.0`
- Phase 8 标记 COMPLETE
- 创建 `v1.0.0` Tag
- GitHub Actions 自动生成 Windows Release

详细步骤见 `docs/PHASE8_ACCEPTANCE.md`。

---

## 第一版范围冻结

v1.0.0 核心仪表：

- Keysight DSO-X 3034A
- Rohde & Schwarz FSW

其他型号、新云服务、数据库索引、PDF 报告等不作为 v1.0.0 必须完成项。
