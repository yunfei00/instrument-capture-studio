# Instrument Capture Studio

面向实验室与研发测试场景的商业化仪表联合采集软件。

v1.0.0 第一版范围固定为：

- Keysight DSO-X 3034A 示波器
- Rohde & Schwarz FSW 频谱分析仪

## 项目定位

Instrument Capture Studio 负责多仪表联合采集产品层；底层通信、SCPI、
驱动、Record/Replay 与单仪表资格验证由 `instrument-automation-platform`
负责。

当前已经具备：

- DSO-X / FSW Adapter
- FSW + DSO-X Combined Capture Workflow
- FSW bounded timeout 与运行中取消
- Job / Step 状态与错误记录
- CSV / NPZ / metadata.json / job.json
- 数据重新加载
- Windows PySide6 GUI
- FSW / DSO-X 后台连接测试
- GUI 开始 / 停止联合采集
- GUI 实时 Capture Step 进度
- 日志与数据浏览

## Windows 本地运行 GUI

推荐把两个仓库放在同一级目录：

```text
workspace/
├── instrument-automation-platform/
└── instrument-capture-studio/
```

在已经准备好的 Python 环境中进入本仓库：

```powershell
git pull --ff-only origin main
python -m pip install -e ".[gui]"
python -m pip install pyvisa pyvisa-py
python scripts/run_gui.py
```

`scripts/run_gui.py` 会自动寻找同级或仓库内的
`instrument-automation-platform`，并把所需 platform package 加入导入路径。

## GUI 联合采集顺序

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

GUI 中的“测试连接”只负责连接、读取身份并自动断开；点击“开始采集”后，
Capture Job 会重新连接两台仪表并执行完整工作流。

## 数据目录

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

## 当前阶段

- Phase 1：完成
- Phase 2：DSO-X 软件接入完成，真机采集待最终补验
- Phase 3：FSW 软件与真机资格验证完成
- Phase 4：联合采集 Software Complete
- Phase 5：数据管理 Software Complete
- Phase 6：商业桌面 UI 开发与实机验收中
- Phase 7：稳定性与产品能力
- Phase 8：最终验收与 v1.0.0 发布

详细进度见 `docs/ROADMAP.md`。
