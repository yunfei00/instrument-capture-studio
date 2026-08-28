# Phase 8 最终对齐与验收清单

目标：在 v1.0.0 发布前冻结真实采集 Recipe / 正式 Schema v1，完成暂停恢复、时间遥测、异常恢复和 Windows 发布验收。

状态定义：

- PASS：已经通过
- SOFTWARE COMPLETE：软件实现已完成，等待真机验收
- PENDING：需要实现或补验
- OPTIONAL：不阻塞 v1.0.0

## 0. 正式数据基线

Phase 8 之前产生的单次数据和 2100 次 Batch 数据均视为开发调试数据，不属于正式数据集，也不要求兼容。Phase 8A 已冻结新的正式 Schema v1，后续正式采集只认该格式。

## A. 已通过的工程基线

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| FSW 真机连接与身份识别 | PASS | 已验证 |
| DSO-X 真机连接与身份识别 | PASS | 已验证 |
| 单次双仪表联合采集 | PASS | GUI 真机通过 |
| FSW bounded timeout | PASS | 真机验证 |
| FSW 运行中取消 / ABORt | PASS | 真机验证 |
| 频率循环批量采集 | PASS | 700–800 MHz / 5 MHz / 21 点 |
| 大规模稳定运行 | PASS | 每频点 100 次，共 2100 次完成；仅作为调试稳定性基线 |
| 参数自动保存 / 恢复 | PASS | 用户验收 |
| 配置模板 | PASS | 用户验收 |
| Spectrum / Waveform 曲线预览 | PASS | 用户验收 |
| Batch HTML 报告 / jobs.csv | PASS | 已切换到正式 Recipe 命名 |
| 全量曲线导出 | PASS | 已切换到正式 Recipe 命名 |
| 固定频率连续采集 | PASS | 用户验收 |
| Windows GUI 打包 | PASS | CI PyInstaller 通过 |
| 主动停止采集 | PASS | CANCELED 后可再次正常采集 |

## B. Phase 8A：正式采集 Recipe / Schema v1

### B1. EXT 联合 + IMM 配对样本

一个逻辑样本固定执行：

1. 配置 FSW 当前中心频率 / Span / RBW / VBW。
2. FSW 切换为 EXT，并先 ARM 进入单次采集等待状态。
3. DSO-X 切换到 DELAY 组时基并执行第一次独立 DIGitize；该硬件事件触发 FSW EXT。
4. 读取 DELAY 测量与本次 DELAY 波形。
5. FSW 等待完成并读取 EXT Spectrum。
6. DSO-X 切换到 CYCLE 组时基并执行第二次独立 DIGitize。
7. 读取 CYCLE_COUNT 与第二次 CYCLE 波形。
8. FSW 切换为 IMM，再采一份同频点 IMM Spectrum。
9. 保存两份频谱、两份示波器波形、测量值与 metadata。

状态：**PASS**

### B2. IMM 频谱单采

只连接 FSW，Trigger 固定 IMM，不要求 DSO-X 在线。

状态：**PASS**

### B3. DSO-X 示波器单采

只连接 DSO-X，不要求 FSW 在线；Waveform Channel 可选 CH1–CH4；仍按 DELAY / CYCLE 两组独立采集。

调试期间出现过 `dsox_delay_group / acquire_word_waveform` VISA Timeout。最终定位为现场 USB→TCP 转接工具把 `:WAVeform:DATA?` 的二进制 IEEE 488.2 block 按 ASCII 文本转换，不是 DSO-X SCPI 指令、Trigger Sweep 或 Acquisition Type 本身的问题。转接工具已改为二进制透明模式。

基于该误判加入的 DSO-X-only `AUTO + NORMal` 隐式改写已从正式 Workflow 撤销；平台仍保留 trigger/acquisition setter 作为正常驱动能力。USB/TCP 转接链路要求已记录到 instrument-automation-platform 的 DSO-X hardware transport 文档。

状态：**PASS**

### B4. 正式数据契约

配对 Job 标准文件：

```text
YYYY-MM-DD/
└── job_id/
    ├── job.json
    ├── metadata.json
    ├── spectrum_ext.csv
    ├── spectrum_ext.npz
    ├── spectrum_imm.csv
    ├── spectrum_imm.npz
    ├── waveform_delay.csv
    ├── waveform_delay.npz
    ├── waveform_cycle.csv
    └── waveform_cycle.npz
```

`metadata.json` 记录 `schema_version = 1`、`recipe`、仪表身份与配置、EXT/IMM 摘要、DELAY/CYCLE_COUNT、两次波形 Channel/点数/时基、Batch/Job 关联和 `capture_complete`。

Data Browser、Trace Viewer、Batch HTML/CSV、全量曲线导出与 preflight 已全部对齐正式命名。

**2026-08-28：Phase 8A COMPLETE，正式 Schema v1 冻结。**

## C. Phase 8B：暂停 / 停止后继续 / 意外退出恢复

已实现：

- 暂停只发生在完整逻辑样本边界。
- PAUSED 时释放 FSW / DSO-X 会话，继续时重新建立会话。
- 已完成样本不重复。
- 主动停止后 Batch 可恢复。
- GUI 重启后可发现未完成正式 Batch，并提供“继续上次任务”。
- 半个逻辑样本不拼接；恢复时使用新的 `-resumeN` Job ID 完整重采。
- 每个正式 Batch 保存 `<output_root>/batch-configs/<batch_id>.json` 冻结参数快照。
- 参数快照包含 Recipe、执行方式、FSW 完整运行参数和 DSO-X 完整运行参数。
- 重启续采以冻结快照为准，不使用当前临时 GUI / QSettings 参数。
- 没有冻结参数快照的旧调试 Batch 不作为正式可续采任务。

真机验收：

- [x] 固定频率重复 10 次，2～3 次后暂停，正确进入 PAUSED。
- [x] 暂停后继续正常，已完成样本不重复。
- [x] 中途主动停止，Batch 保留未完成状态。
- [x] 关闭并重新启动 GUI，可识别“继续上次任务”。
- [x] 续采前故意修改 GUI 参数，程序仍恢复原 Batch 的 Channel 和 DELAY/CYCLE 时基。
- [x] 最终补齐 10/10。
- [x] `batch-configs/<batch_id>.json` 存在并与实际任务一致。

**2026-08-27：Phase 8B COMPLETE。**

## D. Phase 8C：节点耗时与性能统计

已实现：

- Job `started_at / finished_at / duration_ms`
- 每个 Workflow Step 的 started/finished/duration/state/error
- Batch 级 FSW 频率配置耗时
- `fsw_ext_arm`
- `dsox_delay_group`
- `fsw_ext_read`
- `dsox_cycle_group`
- `fsw_imm`
- `save_result`
- 完整 Job
- 成功 Job 的 average / P95 / max
- HTML Batch Report 节点耗时统计
- `timing.csv`

失败 / timeout Job 保留原始耗时用于诊断，但不混入正常性能分布。

状态：**SOFTWARE COMPLETE / HARDWARE DATA REVIEW PENDING**

剩余动作：使用已通过的小批量数据核对 `timing.csv` / HTML 数值是否与实际采集时间量级一致。

## E. Phase 8D：异常与恢复验收

软件侧 Release Hardening 已增加：

- 采集中关闭 GUI 不强制销毁 VISA Worker Thread。
- 关闭请求转换为协作式停止，当前仪表操作安全结束并释放会话后自动退出。
- 连接测试未完成时关闭 GUI，也等待测试结束后再退出。
- 不使用 `QThread.terminate()` 等强制终止方式。
- Release Window 继承 Phase 8B Window，保证冻结参数、暂停/继续和断点续采能力不回退。
- CI Product GUI smoke test 直接实例化 Release Window，并检查安全关闭初始状态和前序 RC 控件。

真机必须完成：

1. FSW 物理断线 → 插回 → 自动恢复。
2. DSO-X 物理断线 → 插回 → 自动恢复；当前现场链路为 USB→TCP Bridge，按真实桥接链路断开/恢复测试。
3. 仪表保持断开直到最大重试次数耗尽，最终明确 FAILED，不无限重试。
4. EXT Trigger Timeout 不误进入 `RECONNECTING`，FSW 安全 ABORt。
5. 采集中关闭 GUI：先安全停止，再自动退出；重新启动后识别未完成任务并可继续。

状态：**IN PROGRESS**

## F. Phase 8E：Windows Release Candidate

正式 v1.0.0 前至少确认：

1. `pytest -q` 通过。
2. `python scripts\phase8_preflight.py --self-check` 通过。
3. GitHub Actions Product GUI smoke test 通过。
4. PyInstaller ZIP 构建通过。
5. Windows EXE 能启动。
6. EXE 下各 Recipe 所需仪表“测试连接”成功。
7. EXE 下三种 Recipe 已完成小规模真机验收。
8. 暂停 / 继续、停止后继续、异常退出恢复完成验收。
9. 正式 Schema v1 的数据浏览、报告、导出、preflight 全部通过。
10. Phase 8D 异常验收全部通过。

状态：PENDING

## G. OPTIONAL，不阻塞 v1.0.0

- PDF 报告
- 更多仪表型号
- 云端报告
- 数据库索引
- UI 主题 / 国际化进一步优化

## Phase 8 顺序

- **8A：正式 Recipe + 正式 Schema v1：COMPLETE**
- **8B：暂停 / 停止后继续 / 意外退出恢复：COMPLETE**
- **8C：节点耗时与性能统计：软件完成，待真机数据复核**
- **8D：断线 / Timeout / GUI 退出异常验收：IN PROGRESS**
- **8E：RC EXE 与 v1.0.0 Release：PENDING**

Phase 7 保持 COMPLETE。Phase 8A 已冻结正式 Schema v1，后续开发重点转为异常恢复和最终发布，不再扩展 v1.0.0 功能范围。
