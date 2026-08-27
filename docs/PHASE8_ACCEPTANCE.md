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
| 单次双仪表联合采集 | PASS | GUI 真机通过，属于旧流程工程验证 |
| FSW bounded timeout | PASS | 真机验证 |
| FSW 运行中取消 / ABORt | PASS | 真机验证 |
| 频率循环批量采集 | PASS | 700–800 MHz / 5 MHz / 21 点 |
| 大规模稳定运行 | PASS | 每频点 100 次，共 2100 次完成；仅作为调试稳定性基线 |
| 参数自动保存 / 恢复 | PASS | 用户验收 |
| 配置模板 | PASS | 用户验收 |
| Spectrum / Waveform 曲线预览 | PASS | 用户验收 |
| Batch HTML 报告 / jobs.csv | PASS | 旧格式能力验证，Phase 8A 需切换到新正式格式 |
| 全量曲线导出 | PASS | 旧格式能力验证，Phase 8A 需切换到新正式格式 |
| 固定频率连续采集 | PASS | 用户验收 |
| Windows GUI 打包 | PASS | CI PyInstaller 通过 |
| 主动停止采集 | PASS | CANCELED 后可再次正常采集 |

## B. v1.0 强制功能对齐：采集 Recipe

GUI 的“采什么数据”和“执行多少次”必须是两个独立维度。

### B1. EXT 联合 + IMM 配对样本

一个逻辑样本固定执行：

1. 配置 FSW 当前中心频率 / Span / RBW / VBW。
2. FSW 切换为 EXT，并先进入单次采集等待状态。
3. 执行 DSO-X 采集，使硬件连接产生 EXT 触发。
4. FSW 等待完成并读取 EXT Spectrum。
5. FSW 切换为 IMM。
6. 再采一份 IMM Spectrum。
7. 保存 DSO-X + EXT Spectrum + IMM Spectrum + metadata。

FSW 必须先 ARM，再让示波器侧产生触发。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

### B2. IMM 频谱单采

只连接 / 使用 FSW：

1. Trigger 固定 IMM。
2. 采一份 Spectrum。
3. 不要求 DSO-X 在线。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

### B3. DSO-X 示波器单采

只连接 / 使用 DSO-X，不要求 FSW 在线。

- Waveform Channel GUI 明确可选 CH1–CH4。
- 首次默认 CH1。
- 后续保存用户上次选择。

状态：**SOFTWARE COMPLETE / HARDWARE PENDING**

## C. Phase 8A 正式数据契约

由于没有需要兼容的正式历史数据，Phase 8A 不继续维护“旧 schema v1 + 新 schema v2”两套格式。

目标是直接收敛为 **正式数据 Schema v1**，由 `recipe` 区分采集内容。

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
    ├── waveform.csv
    └── waveform.npz
```

`metadata.json` 必须明确记录：

- `schema_version = 1`
- `recipe = ext_imm_pair`
- FSW / DSO-X 身份与配置快照
- EXT / IMM 频谱摘要
- DELAY / CYCLE_COUNT
- Waveform Channel / 点数 / Sample Rate
- 当前频率、Batch / Job 关联信息
- capture_complete

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
waveform.csv
waveform.npz
```

`recipe = dsox_only`。

### C4. Phase 8A 收尾要求

- 删除旧 `spectrum` / schema-v1 兼容字段和兼容读取逻辑。
- 删除 schema-v1/schema-v2 双分支。
- Data Browser 识别 `spectrum_ext` / `spectrum_imm`。
- Trace Viewer 可以分别查看 EXT / IMM。
- Batch HTML / CSV / 全量图片导出区分 EXT / IMM。
- preflight 按 Recipe 检查应有文件，不再固定检查旧“6 文件”。
- 所有新测试只围绕正式 Schema v1。

状态：**IN PROGRESS**

## D. Phase 8A 小规模真机验收

正式大规模采集前先执行：

1. EXT + IMM 配对：1 个频点 × 3 个逻辑样本。
2. IMM 单采：1 次。
3. DSO-X 单采：CH1 1 次，再切换其他 Channel 1 次。

重点检查：

- EXT 确实在 FSW ARM 后由示波器侧硬件事件触发。
- 每个逻辑样本的 EXT / IMM / Waveform 没有串样。
- metadata 中 Recipe、频率、Channel、仪表身份正确。
- Job 文件数量和命名完全符合正式 Schema v1。
- GUI 数据浏览和曲线查看正确。
- preflight PASS。

以上通过后，**Phase 8A COMPLETE，正式数据格式冻结**。

## E. Phase 8B：暂停 / 停止后继续 / 意外退出恢复

### E1. 暂停 / 继续

新增“暂停采集”按钮。

- 暂停发生在一个逻辑样本的安全边界。
- 已完成样本不重复。
- GUI 显示 `PAUSED`。
- 点击继续后从下一个未完成逻辑样本继续。

状态：PENDING

### E2. 停止后继续

主动停止释放仪表会话，但 Batch 保留可恢复游标：

- 当前频率索引
- 当前重复次数
- 已完成逻辑样本数
- 未完成逻辑样本

再次点击“继续上次任务”时重新连接仪表，从下一个未完成逻辑样本继续。

状态：PENDING

### E3. 意外退出后恢复

启动 GUI 时扫描未完成 Batch。对于上次处于 `RUNNING / PAUSED / CANCELED` 且未完成的任务，提供“继续上次任务”。

如果程序在一个逻辑样本中途退出，该样本按未完成处理；恢复时重新执行整个逻辑样本，保证 EXT / IMM / DSO-X 配对一致。

状态：PENDING

## F. Phase 8C：节点耗时与性能统计

每个采集节点记录：

- `started_at`
- `finished_at`
- `duration_ms`
- 状态
- 错误（如有）

至少覆盖：FSW 配置、FSW EXT ARM、DSO-X 采集、FSW EXT wait/read、FSW IMM 采集、DELAY、CYCLE_COUNT、Waveform、Save Result 和 Job 总耗时。

Batch 汇总平均值、P95、最大值。

状态：PENDING

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
9. 新正式 Schema v1 的数据浏览、报告、导出、preflight 全部通过。

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
