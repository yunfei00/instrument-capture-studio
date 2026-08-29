# Instrument Capture Studio

面向实验室与研发测试场景的商业化仪表联合采集软件。

v1.0.0 第一版范围固定为：

- Keysight DSO-X 3034A 示波器
- Rohde & Schwarz FSW 频谱分析仪

当前代码版本：**v1.0.0**。正式 Tag 创建后，GitHub Actions 会自动构建 Windows x64 安装包归档并发布 Release。

## 项目定位

Instrument Capture Studio 负责多仪表联合采集产品层；底层通信、SCPI、驱动、Record/Replay 与单仪表资格验证由 `instrument-automation-platform` 负责。

## 当前能力

- 正式 Recipe A：FSW EXT Single + DSO-X 两次 Single + FSW Free Run Single 的同步配对样本
- 正式 Recipe B：FSW IMM / Free Run Single 频谱单采
- 正式 Recipe C：DSO-X 示波器单采，每组波形采集前都执行真实 Single
- 单次采集、固定频率重复采集、频率循环批量采集
- Batch 内仪表长连接复用
- 暂停 / 继续 / 停止后继续 / 程序重启断点续采
- Batch 冻结参数快照，续采恢复原始运行参数
- 连接/通信异常自动重连与有界最大重试
- FSW bounded timeout、取消与安全 ABORt
- EXT Trigger Timeout 与通信掉线区分
- 采集中关闭 GUI 的协作式安全退出
- 参数自动保存 / 恢复、命名实验配置模板
- CSV / NPZ / metadata.json / job.json / batch.json
- Spectrum / Waveform 曲线预览
- Batch HTML 报告、jobs.csv、timing.csv
- 全量正式曲线 SVG 批量导出
- Windows PySide6 GUI / PyInstaller 自动构建与 Tag Release

此前 700–800 MHz、5 MHz 步长、21 点、每频点 100 次的 2100 次运行属于开发调试稳定性验证，不属于最终正式数据集。

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

配对样本支持单次、固定频率重复、频率循环。IMM 单采和示波器单采在 v1.0.0 使用单次执行。

## 最终配对样本顺序

设实时 FSW Sweep Time 为 `T`：

```text
读取 FSW Sweep Time T
    ↓
DSO-X 第一次窗口：MAIN + CENTER
Position = T/2
Scale    = T/10
    ↓
FSW EXT + Continuous OFF + ARM 一次 Single Sweep
    ↓
DSO-X :SINGle #1
等待 armed → 等待 acquisition 完成
    ↓
读取/保存 waveform_sync
同时该物理事件通过触发链路触发 FSW
    ↓
读取 FSW EXT Single → spectrum_ext
    ↓
DSO-X 第二次窗口
默认 Position = 0.484 s
默认 Scale    = 20e-9 s/div
    ↓
DSO-X :SINGle #2
等待完成 → waveform_followup
    ↓
FSW Free Run / IMM
Continuous OFF + 一次 Sweep
    ↓
spectrum_freerun
    ↓
Save Result
```

客户要求的关键规则是：**示波器每次保存波形前必须执行一次前面板等效 Single；频谱每份数据也必须来自一次 Single Sweep。** 正式 DSO-X 路径使用 `:SINGle`，不使用 `:DIGitize` 冒充前面板 Single。

## 正式 Schema v1

配对 Job：

```text
YYYY-MM-DD/
└── job_id/
    ├── job.json
    ├── metadata.json
    ├── spectrum_ext.csv
    ├── spectrum_ext.npz
    ├── waveform_sync.csv
    ├── waveform_sync.npz
    ├── waveform_followup.csv
    ├── waveform_followup.npz
    ├── spectrum_freerun.csv
    └── spectrum_freerun.npz
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

## 发布检查

```powershell
python scripts\phase8_preflight.py --self-check
python scripts\phase8_preflight.py --data-root <数据目录>
```

v1.0.0 发布前确认：CI 全绿；一键完整配对真机确认；小批量快速回归；Windows EXE 启动、连接、采集和数据浏览检查。8 个工程单步已经完成，不需要重新做。

创建 `v1.0.0` Tag 后，`.github/workflows/windows-gui-release.yml` 会自动执行测试、回归、GUI 冒烟测试、PyInstaller 构建，并生成 GitHub Release 与 `InstrumentCaptureStudio-windows-x64.zip`。

## 文档

- `docs/RECIPE_REALIGNMENT.md`：最终真实硬件顺序与 Single 规则
- `docs/PHASE8_ACCEPTANCE.md`：v1.0.0 最终验收清单
- `docs/USER_GUIDE.md`：用户使用说明
- `docs/DEPLOYMENT.md`：Windows 部署与发布
- `docs/ARCHITECTURE.md`：架构边界
- `docs/ROADMAP.md`：开发进度
