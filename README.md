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
- 连接/通信异常自动重连
- Job / Step 状态与错误记录
- CSV / NPZ / metadata.json / job.json
- 数据重新加载
- Windows PySide6 GUI
- FSW / DSO-X 后台连接测试
- GUI 开始 / 停止联合采集
- GUI 实时 Capture Step 进度
- 参数自动保存与恢复
- 命名实验配置模板
- 频率循环 / 批量联合采集
- Batch 长连接、动态中心频率与 `batch.json`
- 大规模 Batch / Job 数据浏览
- Spectrum / Waveform NPZ 曲线预览
- 持久化桌面会话日志
- Batch HTML 报告、完整 Job CSV 和代表频点 SVG 曲线

2026-08-26 已完成一次真实 FSW + DSO-X 大规模批量采集验证：
700–800 MHz、5 MHz 步长、21 个频点、每频点 100 次，共 2100 次完整联合采集。

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

## GUI 单次联合采集顺序

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

## 频率循环 / 批量采集

GUI 可设置：

- 起始中心频率
- 结束中心频率
- 步长
- Span
- 每频点联合采集次数

批量模式正常运行时只建立一次 FSW + DSO-X 长连接，在不同频点之间动态修改
FSW 中心频率；只有连接/通信异常才重新创建 VISA / Driver / Adapter 会话。

每一次联合采集仍然保留独立 Job 和标准数据文件，Batch 额外生成 `batch.json`。

## 数据目录

单次 Job：

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

Batch：

```text
batches/
└── YYYY-MM-DD/
    └── batch_id/
        ├── batch.json
        └── report/
            ├── report.html
            ├── jobs.csv
            └── assets/
```

GUI 数据浏览针对大规模采集只展示最近 Batch / Job，避免一次加载数万个文件项。
双击 NPZ 可直接查看频谱或时域曲线；选择 Batch 后可生成 HTML 报告。

## 配置与日志

常用参数自动保存，下次启动恢复。还可以将完整实验参数保存为命名模板。

默认用户目录：

```text
~/InstrumentCaptureStudio/
├── config/templates/
└── logs/YYYY-MM-DD/
```

## 当前阶段

- Phase 1：完成
- Phase 2：DSO-X 软件接入完成，真机链路已参与联合采集验证
- Phase 3：FSW 软件与真机资格验证完成
- Phase 4：联合采集 Complete
- Phase 5：数据管理 Complete
- Phase 6：商业桌面 UI Baseline Complete
- Phase 7：稳定性与产品能力持续增强，批量扫频基线已通过 2100 次真机采集
- Phase 8：最终异常验收、发布整理与 v1.0.0

详细进度见 `docs/ROADMAP.md`。
