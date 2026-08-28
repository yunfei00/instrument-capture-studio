# Instrument Capture Studio Roadmap

## 目标

第一版完成 Keysight DSO-X 3034A + Rohde & Schwarz FSW 商业化联合采集工具。项目固定为 8 个 Phase；Phase 8 完成后发布 v1.0.0。

## Phase 1–7

状态：**COMPLETE**。

已完成项目架构、DSO-X/FSW 接入、联合 Workflow、CSV/NPZ/Job 数据管理、Windows PySide6 GUI、批量采集、恢复能力、模板、数据浏览、HTML/CSV 报告、SVG 导出及 Windows 构建基线。

2026-08-26 的 700–800 MHz、5 MHz 步长、21 点、每频点 100 次、共 2100 次运行属于开发稳定性验证，不属于最终正式数据集。

## Phase 8 - 验收与商业发布

状态：**IN PROGRESS · v1.0.0 Final RC**。

### Phase 8A - 最终 Recipe / Schema v1

基础实现已经完成。配对 Recipe 在 2026-08-28 经过 8 个硬件单步重新验证后，最终冻结为：

```text
读取 FSW Sweep Time T
→ DSO-X 第一次窗口 Position=T/2、Scale=T/10
→ FSW EXT + Continuous OFF + ARM 一次 Single Sweep
→ DSO-X :SINGle #1，等待完成，读取 waveform_sync
→ 读取 FSW EXT Single → spectrum_ext
→ DSO-X 第二次窗口（默认 0.484 s / 20e-9 s/div）
→ DSO-X :SINGle #2，等待完成，读取 waveform_followup
→ FSW Free Run / IMM + Continuous OFF + 一次 Sweep
→ spectrum_freerun
→ save_result
```

客户最终规则：**所有示波器正式波形都必须先执行一次前面板等效 Single；所有频谱结果也必须来自一次 Single Sweep。** DSO-X 正式路径使用 `:SINGle`，不再把 `:DIGitize` 当作 Single。

配对主数据：

```text
spectrum_ext.csv/.npz
waveform_sync.csv/.npz
waveform_followup.csv/.npz
spectrum_freerun.csv/.npz
```

Schema 仍为 v1；此前 Phase 8 调试文件不承担兼容约束。

状态：**SOFTWARE COMPLETE / FINAL INTEGRATED HARDWARE CHECK PENDING**。

### Phase 8B - 暂停与断点续采

状态：**COMPLETE**。

已完成并真机验收：完整样本边界暂停、PAUSED 释放会话、继续重连、停止后续采、程序重启继续、半 Job 不拼接、`-resumeN` 完整重采、冻结 Batch Runtime Settings。

最终 Single 规则新增的 DSO-X `single_timeout_s` 也进入冻结 Runtime Settings，保证续采行为一致。

最终 Recipe 合入后只需要小批量快速回归，不重新设计 Phase 8B。

### Phase 8C - 节点耗时与性能统计

状态：**SOFTWARE COMPLETE / FINAL DATA REVIEW PENDING**。

最终配对节点为：

```text
fsw_sweep_time
dsox_sync_config
fsw_ext_arm
dsox_sync_capture
fsw_ext_read
dsox_followup_config
dsox_followup_capture
fsw_freerun
save_result
```

继续保存 Job/Step duration、Batch 频率配置耗时、average/P95/max、HTML 节点统计与 `timing.csv`。最终一键真机数据生成后再做时间量级复核。

### Phase 8D - 异常与恢复

状态：**COMPLETE**。

已完成 FSW/DSO-X 通信断开自动恢复、有界最大重试、EXT Trigger Timeout 与掉线区分、FSW ABORt、GUI 协作式安全退出、退出后 Batch 继续。

DSO-X Single 新路径增加有界等待：未 armed 或 acquisition 未完成时超时并 STOP；用户取消同样协作式 STOP。最终 Recipe 合入后只做快速回归。

### Phase 8E - Final RC / v1.0.0

状态：**IN PROGRESS**。

发布前剩余工作：

1. 商业仓库完整 pytest 全绿。
2. FSW ARM/read platform regression 全绿。
3. DSO-X driver regression + `:SINGle` 专项 regression 全绿。
4. preflight、Final RC GUI smoke、PyInstaller Windows ZIP 全绿。
5. 一次完整配对一键真机采集：确认两次 DSO-X Single、EXT Single Sweep、Free Run Single Sweep。
6. 确认一个 Job 四份主数据完整、可打开、互不覆盖。
7. 固定频率小批量 + 暂停/继续快速回归。
8. `timing.csv` / HTML 时间量级复核。

以上完成后：

```text
Phase 8 → COMPLETE
版本 → 1.0.0
创建 v1.0.0 Tag
GitHub Actions → Windows Release
```

## 第一版范围冻结

v1.0.0 只保证 DSO-X 3034A + FSW 当前商业采集需求。PDF 报告、更多仪表型号、云端服务、数据库索引、桥接器 USB 侧特有恢复等不阻塞第一版发布。
