# Instrument Capture Studio

面向实验室与研发测试场景的商业化仪表联合采集软件。

v1.0.0 第一版范围固定为：

- Keysight DSO-X 3034A 示波器
- Rohde & Schwarz FSW 频谱分析仪

当前版本：`0.9.0rc1`，已经进入 Phase 8 最终验收。

## 项目定位

Instrument Capture Studio 负责多仪表联合采集产品层；底层通信、SCPI、驱动、Record/Replay 与单仪表资格验证由 `instrument-automation-platform` 负责。

## 当前能力

- FSW + DSO-X Combined Capture Workflow
- 单次联合采集
- 固定频率连续联合采集
- 频率循环 / 批量联合采集
- Batch 内两台仪表长连接复用
- 连接/通信异常自动重连
- FSW bounded timeout、运行中取消与安全 ABORt
- 参数自动保存 / 恢复
- 命名实验配置模板
- CSV / NPZ / metadata.json / job.json / batch.json
- Spectrum / Waveform 曲线预览
- Batch HTML 报告与完整 jobs.csv
- 全量 Spectrum / Waveform SVG 批量导出
- 长期会话日志
- Windows PySide6 GUI
- Windows PyInstaller 自动构建与 Tag Release

2026-08-26 已完成真实大规模批量验证：700–800 MHz、5 MHz 步长、21 个频点、每频点 100 次，共 2100 次完整联合采集。

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

## 三种采集模式

```text
单次采集
固定频率连续采集
频率循环采集
```

每次完整联合采集顺序：

```text
FSW Spectrum
    ↓
DSO-X DELAY
    ↓
DSO-X CYCLE_COUNT
    ↓
DSO-X Waveform
    ↓
Save Result
```

## 标准 Job 数据目录

```text
YYYY-MM-DD/
└── job_id/
    ├── job.json
    ├── metadata.json
    ├── spectrum.csv
    ├── spectrum.npz
    ├── waveform.csv
    └── waveform.npz
```

批量任务额外保存 `batches/YYYY-MM-DD/<batch_id>/batch.json`。

## Phase 8 发布前检查

运行环境自检：

```powershell
python scripts\phase8_preflight.py --self-check
```

验证最近一个真实 Batch 的数据完整性：

```powershell
python scripts\phase8_preflight.py --data-root <数据目录>
```

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
- Phase 5：完成
- Phase 6：完成基线并真机验收
- Phase 7：完成，包含 2100 次真机大批量验证
- Phase 8：进行中，重点为断线、最大重试、安全退出与正式 Release 验收
