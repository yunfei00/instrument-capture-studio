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

Phase 4 的旧联合采集顺序只作为工程基线；Phase 8A 按真实 EXT ARM → DSO-X → EXT Read → IMM 的业务顺序完成正式 Recipe 对齐。

---

## Phase 5 - 数据管理

状态：**COMPLETE（工程基线）**

已完成 CSV / NPZ、metadata.json、job.json、标准目录、Job ID、仪表身份与配置快照、错误记录、重新加载和跨午夜目录等基础能力。

Phase 5 使用的旧 `spectrum.csv / spectrum.npz` 目录属于开发阶段格式。由于尚未开始正式数据采集，Phase 8A 将直接冻结新的正式数据 Schema v1，不再兼容旧调试数据格式。

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

Phase 8A 会把数据浏览、报告和导出切换到新的正式 Recipe / 数据格式。

---

## Phase 8 - 验收与商业发布

状态：**IN PROGRESS**

当前版本：`0.9.0rc1`

### Phase 8A - 正式 Recipe + 正式数据 Schema v1

状态：**IN PROGRESS**

目标：

- `EXT联合 + IMM配对样本`
- `IMM频谱单采`
- `DSO-X示波器单采`
- 正式数据格式只保留一套 Schema v1
- 删除旧数据兼容分支
- Data Browser / Trace Viewer / Report / Export / preflight 全部适配正式格式
- 1 个频点 × 3 个配对样本 + 两种单仪表 Recipe 小规模真机验收

Phase 8A 通过后，正式数据格式冻结，之后才开始正式批量采集。

### Phase 8B - 暂停与断点续采

状态：**PENDING**

完成暂停 / 继续、停止后继续、意外退出后继续，并保证恢复从下一个完整逻辑样本开始。

### Phase 8C - 节点耗时与性能统计

状态：**PENDING**

记录各采集节点和 Job 总耗时，并提供 Batch 平均值 / P95 / 最大值统计。

### Phase 8D - 异常与恢复真机验收

状态：**PENDING**

完成 FSW / DSO-X 物理断线恢复、最大重试失败、Trigger Timeout 不误重连、采集中关闭 GUI 的安全退出与恢复。

### Phase 8E - Release Candidate

状态：**PENDING**

完成新正式格式 preflight、Windows EXE 真机验收、三种 Recipe 验收以及最终发布检查。

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
