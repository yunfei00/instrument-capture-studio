# Phase 8 最终对齐与验收清单

目标：在 v1.0.0 发布前先把真实采集业务语义和正式数据格式冻结，再完成暂停恢复、异常恢复、数据完整性和 Windows 发布验收。

状态定义：

- PASS：已经通过
- SOFTWARE COMPLETE：软件实现已完成，等待真机验收
- PENDING：需要实现或补验
- OPTIONAL：不阻塞 v1.0.0

## 0. 正式数据基线清零

当前仍处于开发 / 调试阶段，**尚未开始正式数据采集**。

因此从 Phase 8 开始采用以下原则：

- 之前产生的单次数据、2100 次 Batch 数据等全部视为调试数据。
- 调试数据可以全部删除，不作为正式数据资产保留。
- 不要求兼容之前的 Job 数据目录、metadata schema 或旧的 `spectrum.csv / spectrum.npz` 文件命名。
- 不为旧数据保留迁移器、兼容读取分支或双 schema 维护逻辑。
- Phase 8A 直接冻结一套新的正式数据契约，后续正式采集只认这一套格式。
- 在正式数据契约冻结之前，不再进行大规模正式采集。

之前 700–800 MHz、21 点、每点 100 次、共 2100 次运行仍然保留其工程意义：它证明了批量循环、长连接和稳定性基线能够工作，但它**不是正式训练数据集**。

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

## B. v1.0 强制功能对齐：采集 Recipe

GUI 的“采什么数据”和“执行多少次”是两个独立维度。

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

FSW 必须先 ARM，再让示波器侧产生触发。第二次示波器采集必须发生在 EXT Spectrum 已读取之后。

状态：**PASS（单次真实配对样本已真机验证）**

### B2. IMM 频谱单采

只连接 / 使用 FSW：

1. Trigger 固定 IMM。
2. 采一份 Spectrum。
3. 不要求 DSO-X 在线。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

### B3. DSO-X 示波器单采

只连接 / 使用 DSO-X，不要求 FSW 在线。

- Waveform Channel GUI 明确可选 CH1–CH4。
- 首次默认 CH1，后续保存用户上次选择。
- 仍按 DELAY 组和 CYCLE 组执行两次独立示波器采集。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

## C. Phase 8A 正式数据契约

由于没有需要兼容的正式历史数据，正式格式从 **Schema v1** 起步，由 `recipe` 区分采集内容。

### C1. EXT + IMM 配对样本

标准 Job：

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

`metadata.json` 明确记录：

- `schema_version = 1`
- `recipe = ext_imm_pair`
- FSW / DSO-X 身份与配置快照
- EXT / IMM 频谱摘要
- DELAY / CYCLE_COUNT 测量值
- 两次 Waveform 的 Channel / 点数 / Sample Rate / 时基
- 当前频率、Batch / Job 关联信息
- `capture_complete`

### C2. IMM 频谱单采

```text
job.json
metadata.json
spectrum_imm.csv
spectrum_imm.npz
```

`recipe = imm_spectrum_only`。

### C3. DSO-X 示波器单采

```text
job.json
metadata.json
waveform_delay.csv
waveform_delay.npz
waveform_cycle.csv
waveform_cycle.npz
```

`recipe = dsox_only`，DELAY / CYCLE_COUNT 测量值保存在 metadata。

### C4. Phase 8A 软件收尾

- 正式 Recipe 不依赖旧 generic `spectrum / waveform` 文件命名。
- 正式 Schema 统一为 v1。
- Data Browser 识别 EXT / IMM / DELAY / CYCLE 四类数据。
- Trace Viewer 可以分别查看四类 NPZ。
- Batch HTML / CSV / 全量图片导出区分四类数据。
- preflight 按 Recipe 检查应有文件，不再固定检查旧“6 文件”。
- 所有正式新测试围绕 Schema v1。

状态：**SOFTWARE COMPLETE**

## D. Phase 8A 小规模真机验收

当前：

- [x] EXT + IMM 配对：真实单次采集通过，四类数据文件均正确生成。
- [ ] IMM 单采：1 次。
- [ ] DSO-X 单采：CH1 1 次；可再用 CH2 验证通道切换。

重点检查：

- EXT 确实在 FSW ARM 后由第一次 DSO-X DELAY 组硬件事件触发。
- 第二次 CYCLE 组采集不会干扰已经完成的 EXT 样本。
- 每个逻辑样本的 EXT / IMM / DELAY / CYCLE 没有串样。
- metadata 中 Recipe、频率、Channel、时基、仪表身份正确。
- Job 文件数量和命名符合正式 Schema v1。
- GUI 数据浏览和曲线查看正确。
- preflight PASS。

以上通过后，**Phase 8A COMPLETE，正式数据格式冻结**。

## E. Phase 8B：暂停 / 停止后继续 / 意外退出恢复

### E1. 暂停 / 继续

软件行为：

- GUI 提供“暂停采集”。
- 暂停只发生在一个完整逻辑样本的安全边界。
- 进入 PAUSED 后释放 FSW / DSO-X 会话。
- 已完成样本不重复。
- 点击继续后重新建立会话，从下一条未完成逻辑样本继续。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

### E2. 停止后继续

主动停止释放仪表会话，Batch 保留：

- 当前频率索引
- 当前重复次数
- 已完成逻辑样本集合
- 未完成逻辑样本
- `batch.json` checkpoint

再次点击“继续上次任务”时从未完成逻辑样本继续。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

### E3. 意外退出后恢复

启动 GUI 时扫描 `RUNNING / PAUSED / CANCELED / FAILED` 且仍未完成的正式 Batch。

如果程序在一个逻辑样本中途退出，该样本按未完成处理；恢复时使用新的 `-resumeN` Job ID 重新执行整个逻辑样本，不会把半旧 EXT/IMM/DSO-X 数据和新数据拼接。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

### E4. 原任务参数冻结

每个正式 Batch 保存独立参数快照：

```text
<output_root>/batch-configs/<batch_id>.json
```

快照包含：

- Recipe
- 原执行方式（frequency sweep / fixed repeat）
- FSW VISA resource / backend / transport timeout / step timeout / center / span / RBW / VBW / trigger
- DSO-X VISA resource / backend / transport timeout / DELAY source/edge / CYCLE source / Channel / DELAY 时基 / CYCLE 时基

程序重启后续采以该快照为准，不读取用户此时临时修改后的 GUI / QSettings 作为任务参数。没有冻结参数快照的旧调试 Batch 不会作为正式可续采任务提供。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

### E5. Phase 8B 真机验收动作

固定频率重复 10 次：

1. 正常完成 2～3 个样本后点击暂停。
2. 确认只在完整样本边界进入 PAUSED。
3. 点击继续并再完成若干样本。
4. 点击停止，确认 Batch 仍可恢复。
5. 关闭 GUI。
6. 重新打开 GUI，并在点击“继续上次任务”前临时改动一个明显参数（例如 Channel 或时基）。
7. 点击“继续上次任务”，确认界面恢复原 Batch 参数，实际采集也使用原参数。
8. 最终补齐 10/10。
9. 确认已成功样本没有重复；重启后的未完成样本目录使用 `-resume1`（后续再次恢复则递增）。
10. 确认 `<output_root>/batch-configs/<batch_id>.json` 存在。

状态：**PENDING**

## F. Phase 8C：节点耗时与性能统计

每个 Job 已记录：

- `started_at`
- `finished_at`
- `duration_ms`
- 每个 Workflow Step 的状态 / 错误 / duration

正式配对流程的逻辑节点包括：

- Batch 级 FSW 频率配置
- `fsw_ext_arm`
- `dsox_delay_group`
- `fsw_ext_read`
- `dsox_cycle_group`
- `fsw_imm`
- `save_result`
- 完整 Job

Batch 报告从成功 Job 的持久化 `job.json` 汇总：

- 样本数
- average
- P95
- max

同时生成 `timing.csv`；失败 / timeout Job 保留原始耗时用于诊断，但不混入正常性能分布。

状态：**SOFTWARE COMPLETE / HARDWARE DATA REVIEW PENDING**

## G. Phase 8D：异常与恢复验收

必须完成：

1. FSW 物理断线 → 插回 → 自动恢复。
2. DSO-X 物理断线 → 插回 → 自动恢复。
3. 仪表保持断开直到最大重试次数耗尽。
4. EXT Trigger Timeout 不误进入 `RECONNECTING`，FSW 安全 ABORt。
5. 采集中关闭 GUI 时安全停止；再次启动可识别未完成任务。

状态：PENDING

## H. Phase 8E：Windows Release Candidate

正式 v1.0.0 前至少确认：

1. `pytest -q` 通过。
2. `python scripts\phase8_preflight.py --self-check` 通过。
3. GitHub Actions Product GUI smoke test 通过。
4. PyInstaller ZIP 构建通过。
5. Windows EXE 能启动。
6. EXE 下各 Recipe 所需仪表“测试连接”成功。
7. EXE 下三种 Recipe 完成小规模真机验收。
8. 暂停 / 继续、停止后继续、异常退出恢复完成验收。
9. 正式 Schema v1 的数据浏览、报告、导出、preflight 全部通过。
10. Batch 报告可查看节点耗时 average / P95 / max，并导出 timing.csv。

状态：PENDING

## I. OPTIONAL，不阻塞 v1.0.0

- PDF 报告
- 更多仪表型号
- 云端报告
- 数据库索引
- UI 主题 / 国际化进一步优化

## 新 Phase 8 顺序

- **8A：正式 Recipe + 正式数据 Schema v1 + 小规模真机冻结**
- **8B：暂停 / 停止后继续 / 意外退出恢复**
- **8C：节点耗时与性能统计**
- **8D：断线 / Timeout / GUI 退出等异常验收**
- **8E：RC EXE 与 v1.0.0 Release**

Phase 7 保持 COMPLETE，不重新打开。之前数据全部按调试数据处理，Phase 8A 通过后才开始正式数据采集。
