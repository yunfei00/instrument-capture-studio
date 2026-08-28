# Final Paired Recipe Realignment

状态：**8 个单步真机验证已全部通过；正式一键 Workflow 已合成，当前进入 Final RC 真机确认。**

本轮冻结的是 v1.0.0 的真实硬件采集顺序。Phase 8B 的暂停/续采、Phase 8D 的断线恢复/Timeout/安全退出继续沿用，不重新设计。

## 1. Single 的业务要求

客户要求所有真正写入数据集的物理采集都必须是一次性采集：

- DSO-X：每次保存波形前都必须等效按一次前面板 **Single**。软件使用 `:SINGle`，等待示波器进入 armed 并完成这一次 acquisition 后，才读取/保存该次 Waveform。正式流程不再用 `:DIGitize` 代替 Single。
- FSW：每份频谱都只做一次 Sweep。底层使用 `INITiate:CONTinuous OFF` 后执行一次 `INITiate`；EXT 场景先 ARM 等外部触发，Free Run / IMM 场景立即完成这一次 Sweep。

因此一个逻辑样本里不存在“运行中随便读当前屏幕缓存”的数据；每个文件都对应一次明确的一次性采集。

## 2. FSW 配置边界

正式测试前由测试人员在 FSW 前面板准备当前测量，包括中心频率、Span、RBW、VBW、Sweep Time 等。

固定频率单次/重复模式不在每个逻辑样本开始时覆盖这些测量参数。工具只负责读取 Sweep Time、切换 EXT / IMM Trigger、执行 Single Sweep，以及读取结果。

只有“频率循环”执行模式明确拥有中心频率/Span 扫描计划，软件才按计划切换频点；RBW、VBW、Sweep Time 等仍保持测试配置。

## 3. 最终正式硬件顺序

设实时读取到的 FSW Sweep Time 为 `T`：

1. 读取 FSW `SENSe:SWEep:TIME?`。
2. DSO-X 第一次同步窗口：MAIN + CENTER，`Position=T/2`，`Scale=T/10`，并 Query 回读。
3. FSW Trigger=`EXT`，`INITiate:CONTinuous OFF`，ARM 一次 Single Sweep。
4. DSO-X 执行 `:SINGle`；等待 armed 和本次 acquisition 完成；随后读取并保存 `waveform_sync`。该次物理采集事件通过客户触发链路触发已经 ARM 的 FSW。
5. 等待 FSW EXT Single Sweep 完成并读取 `spectrum_ext`。
6. DSO-X 第二次窗口：Position、Scale 使用 GUI 保存参数；当前默认 `0.484 s`、`20e-9 s/div`，并 Query 回读。
7. DSO-X 再执行一次独立 `:SINGle`；等待完成后读取并保存 `waveform_followup`。
8. FSW Trigger=`IMM` / Free Run，连续模式 OFF，只执行一次 Sweep，保存 `spectrum_freerun`。
9. 四份数据共同组成一个完整逻辑样本。

正式软件节点：

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

## 4. 正式数据契约

配对 Job 的主数据文件为：

```text
job.json
metadata.json
spectrum_ext.csv
spectrum_ext.npz
waveform_sync.csv
waveform_sync.npz
waveform_followup.csv
waveform_followup.npz
spectrum_freerun.csv
spectrum_freerun.npz
```

`metadata.json` 同时保存 Sweep Time、两次 DSO-X 时间窗口回读值、Waveform Channel、仪表信息，以及四次物理采集的 Single 语义。历史开发调试数据不承担兼容约束。

## 5. 单步调试入口

“工程调试 / 单步采集”仍保留，但定位已经从“决定正式流程”变为现场诊断工具。此前 8 个真机步骤已经全部 PASS；正常正式采集直接使用一键 Recipe。

如果以后现场某一步异常，可再使用该入口定位 Sweep Time、时间窗口、EXT ARM、第一次同步采集、EXT Read、第二次采集和 Free Run，而不改变正式数据契约。

## 6. v1.0.0 最后门槛

当前不再重做 8 个单步。Final RC 只需要完成一次新的完整一键真机确认：

- DSO-X 屏幕/状态能够观察到两次独立 Single；每次完成后才读取对应 Waveform。
- FSW EXT 是一份 Single Sweep，并由第一次 DSO-X 采集触发。
- FSW Free Run / IMM 也是一份 Single Sweep。
- 一个 Job 最终有四份正确且互不覆盖的主数据。
- 随后做小批量、恢复能力与 Release preflight 快速回归。

该确认通过后才创建正式 `v1.0.0` Tag / Release。
