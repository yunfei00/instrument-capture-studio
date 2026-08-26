# Instrument Capture Studio 用户指南

适用版本：v0.9.0 RC / v1.0.0

第一版固定支持：

- Keysight DSO-X 3034A
- Rohde & Schwarz FSW

## 1. 启动

源码运行：

```powershell
python scripts/run_gui.py
```

发布包运行：解压 Windows ZIP 后启动 `InstrumentCaptureStudio.exe`。

## 2. 仪表地址与连接

分别填写 FSW 与 DSO-X 的 VISA 地址，点击“测试连接”。

“测试连接”只执行：连接 → 读取仪表身份 → 断开。真正开始采集时软件会重新建立会话。

常用参数会自动保存，下一次启动自动恢复。

## 3. 采集模式

### 单次采集

执行一次完整联合采集：

```text
FSW Spectrum
→ DSO-X DELAY
→ DSO-X CYCLE_COUNT
→ DSO-X Waveform
→ Save Result
```

### 频率循环采集

配置：起始频率、结束频率、步长、Span、每频点采集次数。

例如：700–800 MHz、步长 5 MHz、每频点 100 次，共 21 个频点、2100 次联合采集。

Batch 正常运行期间复用两台仪表长连接，只在真实连接/通信故障时重新建立会话。

### 固定频率连续采集

使用当前 FSW Center / Span，在同一频率下连续执行用户指定次数的完整联合采集，同样复用长连接。

## 4. 停止采集

点击“停止采集”后软件发送协作式取消请求。正在执行的仪表操作会在安全边界结束或中止，然后退出当前 Job / Batch。

不要使用任务管理器强制结束作为正常停止方式。

## 5. 数据目录

每次成功 Job 保存：

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

批量任务额外保存：

```text
batches/
└── YYYY-MM-DD/
    └── batch_id/
        └── batch.json
```

## 6. 数据浏览与曲线

数据浏览区域支持：

- 双击 Job 打开目录
- 双击 `batch.json` / `job.json` / `metadata.json` 查看结构化内容
- 双击 `spectrum.npz` 查看频谱曲线
- 双击 `waveform.npz` 查看时域波形

大数组会自动抽样用于预览，不修改原始数据。

## 7. 配置模板

输入模板名称后点击“保存模板”，可保存当前 VISA、FSW、DSO-X、采集模式、扫频参数和输出目录。

以后选中模板并点击“加载模板”即可恢复整套实验参数。

## 8. Batch 报告与批量转图

选中一个 Batch 后可以：

- 生成 HTML 报告：每频点选择代表性成功 Job，生成 Spectrum / Waveform SVG，并导出完整 `jobs.csv`
- 导出全部曲线：将所有成功 Job 的 Spectrum / Waveform 转为 SVG，同时生成索引 CSV

大批量导出在后台执行，不阻塞 GUI 主界面。

## 9. 日志

GUI 日志同时写入用户目录中的会话日志。遇到掉线、超时、重连或异常时，优先保留：

- 会话日志
- 对应 Job 的 `job.json`
- Batch 的 `batch.json`

这些文件用于定位问题。

## 10. 自动重连规则

自动重连只针对：

- InstrumentConnectionError
- InstrumentCommunicationError

默认最多 4 次完整 Capture 尝试，重连等待 2 秒。

Trigger / Measurement Timeout 不自动重连，因为“没有触发”不等于“网络断开”。

## 11. 发布前数据校验

可校验最近一个 Batch：

```powershell
python scripts/phase8_preflight.py --data-root D:\capture-data
```

或指定 `batch.json`：

```powershell
python scripts/phase8_preflight.py --batch D:\capture-data\batches\2026-08-26\batch-xxxx\batch.json
```

PASS 表示 Batch 完成数量一致，并且每个成功 Job 的 6 个标准文件完整存在。
