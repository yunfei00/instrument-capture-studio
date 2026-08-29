# Instrument Capture Studio 用户指南

适用版本：v1.0.0 Final RC / v1.0.0

第一版固定支持：Keysight DSO-X 3034A + Rohde & Schwarz FSW。

## 1. 商业版主界面

v1.0.0 使用左侧导航 + 右侧工作区，不再把连接、采集、数据、模板、调试和日志堆在同一个页面。

左侧固定六个工作区：

- **任务采集**：选择 Recipe / 执行方式、配置批量任务、开始 / 暂停 / 停止 / 继续任务。
- **仪表连接**：配置 FSW 与 DSO-X VISA 地址、仪表参数并执行连接测试。
- **数据与报告**：浏览 Batch / Job、查看曲线、生成 HTML 报告并批量导出正式曲线。
- **配置模板**：保存、加载和删除常用实验配置。
- **工程调试**：保留八步单步采集，用于研发、交付和售后问题定位；普通测试无需进入。
- **设置与日志**：查看当前数据目录、会话日志和实时运行日志。

窗口顶部始终显示 FSW、DSO-X、当前任务和数据目录的快速状态，切换页面不会影响正在执行的采集任务。

## 2. 启动与连接

源码运行：

```powershell
python scripts\run_gui.py
```

发布包运行：解压 Windows ZIP 后启动 `InstrumentCaptureStudio.exe`。

进入“仪表连接”页，分别填写 FSW 与 DSO-X 的 VISA 地址并点击“测试连接”。测试连接只做连接、身份读取、断开；正式采集会重新建立会话。常用参数自动保存。

## 3. 采集内容

### EXT 联合 + IMM 配对样本

这是正式联合数据 Recipe。每个逻辑样本严格执行：

```text
读取 FSW Sweep Time T
→ DSO-X 第一次窗口 Position=T/2、Scale=T/10
→ FSW EXT，Continuous OFF，ARM 一次 Single Sweep
→ DSO-X :SINGle #1，等待完成后读取 waveform_sync
→ 读取已完成的 FSW EXT Single → spectrum_ext
→ DSO-X 第二次窗口（默认 Position=0.484 s、Scale=20e-9 s/div）
→ DSO-X :SINGle #2，等待完成后读取 waveform_followup
→ FSW Free Run / IMM，Continuous OFF，只做一次 Sweep → spectrum_freerun
→ Save Result
```

客户规则：**示波器每份保存的波形前都必须执行一次真正的 Single；频谱每份结果也必须来自一次 Single Sweep。** 软件不会把连续运行中的当前屏幕数据直接当作正式样本。

### IMM 频谱单采

只连接 FSW。Trigger=IMM，Continuous OFF，只执行一次 Sweep，完成后保存频谱。

### DSO-X 示波器单采

只连接 DSO-X。DELAY 与 CYCLE 两组分别设置参数；每一组都执行一次 `:SINGle`，等待该次采集完成后再读取/保存波形。两组是两个独立 acquisition。

## 4. 执行方式

配对 Recipe 支持：

- 单次采集
- 固定频率连续采集
- 频率循环采集

频率循环可以配置起始频率、结束频率、步长、Span、每频点次数。Batch 正常运行期间复用仪表长连接，只在真实连接/通信故障时重新建立会话。

固定频率重复模式保持测试人员当前 FSW 测量设置；频率循环模式才按计划修改中心频率/Span。

## 5. DSO-X 时间窗口

配对 Recipe 的第一次窗口由 FSW 当前 Sweep Time 自动计算，不需要人工填写：

```text
Position = T / 2
Scale    = T / 10
```

第二次窗口由 GUI 配置并自动保存，默认：

```text
Position = 0.484 s
Scale    = 20e-9 s/div
```

## 6. 停止、暂停与继续

“停止采集”发送协作式取消请求，不使用强制杀线程。批量任务的“暂停”只在完整逻辑样本边界生效；暂停时释放仪表会话，继续时重新建立会话。

未完成 Batch 可以在重新启动 GUI 后选择“继续上次任务”。已成功的逻辑样本不会重复；未完成的半个 Job 不拼接，而是重新完整采集。

## 7. 正式数据目录

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

IMM-only：`job.json`、`metadata.json`、`spectrum_imm.csv/.npz`。

DSO-X-only：`job.json`、`metadata.json`、`waveform_delay.csv/.npz`、`waveform_cycle.csv/.npz`。

批量任务额外保存：

```text
batches/YYYY-MM-DD/<batch_id>/batch.json
batch-configs/<batch_id>.json
```

## 8. 数据浏览、报告和导出

进入“数据与报告”页，可以打开 Job/Batch 目录、JSON 和四类正式 NPZ 曲线。大数组仅在预览时抽样，不修改原始文件。

Batch 可以生成 HTML 报告、`jobs.csv`、`timing.csv`，也可以把所有正式曲线批量导出为 SVG。

## 9. 配置模板与参数保存

GUI 参数自动保存。进入“配置模板”页可以保存/加载整套参数，包括 VISA、FSW 参数、执行方式、扫频计划、输出目录、Waveform Channel 和第二次 DSO-X Position/Scale。

## 10. 异常与自动恢复

连接/通信异常使用有界重连；Trigger Timeout 不等同于网络断线，因此不会误进入重连。FSW 超时会安全 ABORt；DSO-X Single 等待超时会 STOP，不会无限等待。

默认恢复策略最多 4 次完整 Capture 尝试，重连间隔 2 秒。

## 11. 工程调试入口

“工程调试”页保留“工程调试 / 单步采集”入口，用于现场故障定位。正式同步流程的 8 个单步已经完成真机验收，正常使用不需要进入该窗口。

## 12. 发布前数据校验

运行环境：

```powershell
python scripts\phase8_preflight.py --self-check
```

校验最近 Batch：

```powershell
python scripts\phase8_preflight.py --data-root D:\capture-data
```

或指定：

```powershell
python scripts\phase8_preflight.py --batch D:\capture-data\batches\YYYY-MM-DD\batch-id\batch.json
```

PASS 表示 Batch 完成数量一致，且每个成功 Job 的当前 Recipe 所要求的正式文件完整存在。
