# Instrument Capture Studio

面向实验室与研发测试场景的商业化仪表联合采集软件。

v1.0.0 第一版范围固定为：

- Keysight DSO-X 3034A 示波器
- Rohde & Schwarz FSW 频谱分析仪

当前版本：`1.0.0rc1`，已经进入 Phase 8E Release Candidate 最终验收。

## 项目定位

Instrument Capture Studio 负责多仪表联合采集产品层；底层通信、SCPI、驱动、Record/Replay 与单仪表资格验证由 `instrument-automation-platform` 负责。

## 当前能力

- 正式 Recipe A：FSW EXT + DSO-X DELAY/CYCLE + 同频点 FSW IMM 配对样本
- 正式 Recipe B：FSW IMM 频谱单采
- 正式 Recipe C：DSO-X 示波器单采
- 单次采集
- 固定频率连续采集
- 频率循环 / 批量联合采集
- Batch 内两台仪表长连接复用
- 暂停 / 继续 / 停止后继续 / 程序重启断点续采
- Batch 冻结参数快照，续采恢复原始仪表参数
- 连接/通信异常自动重连与有界最大重试
- FSW bounded timeout、运行中取消与安全 ABORt
- EXT Trigger Timeout 与通信掉线区分，不误触发重连
- 采集中关闭 GUI 的协作式安全退出
- 参数自动保存 / 恢复
- 命名实验配置模板
- 正式 Schema v1 的 CSV / NPZ / metadata.json / job.json / batch.json
- Spectrum / Waveform 曲线预览
- Batch HTML 报告、jobs.csv、timing.csv
- 全量正式曲线 SVG 批量导出
- 长期会话日志
- Windows PySide6 GUI
- Windows PyInstaller 自动构建与 Tag Release

2026-08-26 已完成真实大规模调试稳定性验证：700–800 MHz、5 MHz 步长、21 个频点、每频点 100 次，共 2100 次完整联合采集。该批数据属于开发调试数据，不属于正式数据集。

## Windows 本地运行 GUI

推荐两个仓库同级：

```text
workspace/
├── instrument-automation-platform/
└── instrument-capture-studio/
```

```powershell
cd instrument-automation-platform
git pull --ff-only origin main

cd ..\instrument-capture-studio
git pull --ff-only origin main
python -m pip install -e ".[gui]"
python -m pip install pyvisa pyvisa-py
python scripts\run_gui.py
```

## 采集内容与执行方式

采集内容：

```text
EXT联合 + IMM配对样本
IMM频谱单采
示波器单采
```

配对样本支持执行方式：

```text
单次采集
固定频率连续采集
频率循环采集
```

IMM 单采和示波器单采在 v1.0.0 先使用单次采集。

## 正式 EXT + IMM 配对样本顺序

```text
FSW 配置当前频点
    ↓
FSW EXT ARM
    ↓
DSO-X DELAY 组：5e-7 s/div，第一次独立 DIGitize
    ↓
读取 DELAY + waveform_delay
    ↓
FSW EXT wait/read
    ↓
DSO-X CYCLE 组：1e-4 s/div，第二次独立 DIGitize
    ↓
读取 CYCLE_COUNT + waveform_cycle
    ↓
FSW IMM
    ↓
Save Result
```

一个配对 Job 是一个完整逻辑训练样本；EXT、IMM、DELAY 波形、CYCLE 波形不能跨 Job 拼接。

## 正式 Schema v1

配对 Job：

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

IMM-only：

```text
job.json
metadata.json
spectrum_imm.csv
spectrum_imm.npz
```

DSO-X-only：

```text
job.json
metadata.json
waveform_delay.csv
waveform_delay.npz
waveform_cycle.csv
waveform_cycle.npz
```

批量任务额外保存：

```text
batches/YYYY-MM-DD/<batch_id>/batch.json
batch-configs/<batch_id>.json
```

`batch-configs` 保存正式续采使用的冻结仪表参数快照。

## Phase 8 发布前检查

运行环境自检：

```powershell
python scripts\phase8_preflight.py --self-check
```

验证最近一个真实 Batch 的数据完整性：

```powershell
python scripts\phase8_preflight.py --data-root <数据目录>
```

Batch HTML 报告同时输出 `jobs.csv` 和 `timing.csv`，用于最终数据与节点耗时复核。

## 文档

- `docs/USER_GUIDE.md`：用户使用说明
- `docs/DEPLOYMENT.md`：Windows 部署与发布
- `docs/PHASE8_ACCEPTANCE.md`：v1.0.0 最终验收清单
- `docs/ARCHITECTURE.md`：架构边界
- `docs/ROADMAP.md`：完整开发进度

## 当前阶段

- Phase 1：完成
- Phase 2：完成
- Phase 3：完成
- Phase 4：完成
- Phase 5：完成工程基线
- Phase 6：完成基线并真机验收
- Phase 7：完成，包含 2100 次真机调试稳定性验证
- Phase 8A：完成，正式 Recipe / Schema v1 冻结
- Phase 8B：完成，暂停与断点续采真机通过
- Phase 8C：软件完成，等待最终 timing.csv / HTML 真机时间量级复核
- Phase 8D：完成，断线、最大重试、Trigger Timeout、安全退出真机通过
- Phase 8E：进行中，Release Candidate Windows 构建与最终发布验收
