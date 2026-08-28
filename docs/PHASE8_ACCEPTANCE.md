# Phase 8 最终对齐与验收清单

目标：在 v1.0.0 发布前冻结真实采集 Recipe / Schema v1，保留已经完成的暂停恢复、异常恢复与发布能力，并完成最终 Single 一键流程真机确认。

当前版本：**v1.0.0 Final RC，尚未打正式 v1.0.0 Tag。**

## 0. 正式数据原则

Phase 8 之前及 Recipe 重对齐期间产生的数据均视为开发调试数据，不要求向后兼容。最终配对 Recipe 的一个完整 Job 必须包含四份主数据：

```text
spectrum_ext.csv / .npz
waveform_sync.csv / .npz
waveform_followup.csv / .npz
spectrum_freerun.csv / .npz
```

同时保存 `job.json` 与 `metadata.json`。正式 Schema 版本仍为 `1`，但最终数据契约以本文件和 `RECIPE_REALIGNMENT.md` 当前内容为准。

## A. 已通过的工程基线

| 项目 | 状态 |
| --- | --- |
| FSW 真机连接 / 身份识别 | PASS |
| DSO-X 真机连接 / 身份识别 | PASS |
| FSW bounded timeout / ABORt | PASS |
| 批量频率循环与大规模调试稳定性 | PASS |
| 参数保存 / 恢复、模板、曲线预览 | PASS |
| Batch HTML / CSV / 全量曲线导出 | PASS |
| 固定频率重复采集 | PASS |
| 暂停 / 继续 / 停止后续采 | PASS |
| FSW / DSO-X 断线自动恢复 | PASS |
| GUI 安全退出 | PASS |
| 新同步流程 8 个硬件单步 | PASS |

## B. 最终配对 Recipe：全部使用 Single

客户最终要求：**示波器保存波形前必须按一次 Single；频谱也必须是 Single Sweep。**

最终一个逻辑样本执行：

1. 读取实时 FSW Sweep Time `T`。
2. DSO-X：MAIN + CENTER，第一次 `Position=T/2`、`Scale=T/10`，并回读确认。
3. FSW：Trigger=`EXT`，Continuous OFF，ARM 一次 Single Sweep。
4. DSO-X：执行 `:SINGle`，等待 armed 和本次 acquisition 完成，再读取/保存 `waveform_sync`；该物理事件通过客户触发链路触发 FSW。
5. 等待并读取本次 EXT Single Sweep，保存 `spectrum_ext`。
6. DSO-X：配置第二次 Position/Scale，默认 `0.484 s` / `20e-9 s/div`，并回读确认。
7. DSO-X：再次执行独立 `:SINGle`，完成后读取/保存 `waveform_followup`。
8. FSW：Trigger=`IMM` / Free Run，Continuous OFF，只执行一次 Sweep，保存 `spectrum_freerun`。
9. 四份主数据完整后才允许 `save_result` 成功。

正式节点：

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

状态：**SOFTWARE COMPLETE / FINAL INTEGRATED HARDWARE CHECK PENDING**。

## C. 单仪表 Recipe

### C1. IMM 频谱单采

只连接 FSW，Trigger=`IMM`；Continuous OFF，只执行一次 INIT/Sweep，完成后保存 `spectrum_imm`。

状态：**SOFTWARE COMPLETE**。

### C2. DSO-X 单采

只连接 DSO-X。DELAY 与 CYCLE 仍作为两个独立组；每组都先设置该组参数，再执行一次真实 `:SINGle`，等待完成后读取对应波形。两组不复用同一 acquisition。

状态：**SOFTWARE COMPLETE / Single 改造后待快速真机确认**。

## D. Single 实现验收要求

DSO-X platform 的 Single 路径必须满足：

- `:SINGle` 等效前面板 Single，不用 `:DIGitize` 冒充。
- 发送 Single 前清除旧 Arm Event。
- 用 `:AER?` 确认本次 acquisition 已进入 armed。
- 用 `:OPERegister:CONDition?` 的 RUN 位确认本次 acquisition 已结束。
- 结束后才读取 PREamble / byte order / unsigned / binary waveform。
- Trigger 不到时必须有界超时并 `:STOP`，不能无限挂起。
- 用户取消时协作式停止。

FSW Single 路径必须满足：

- EXT：Continuous OFF + 一次 INIT 后等待外部 Trigger。
- IMM：Continuous OFF + 一次 INIT，完成后读取。
- 不允许后台 Continuous Sweep 的任意当前 Trace 被当作正式样本保存。

## E. Batch 暂停 / 续采 / 冻结参数

既有 Phase 8B 能力继续有效：

- 只在完整逻辑样本边界暂停。
- PAUSED 时释放仪表会话，继续时重连。
- 已成功样本不重复。
- 半个 Job 不拼接；恢复后新 Job 完整重采。
- Batch 参数快照独立保存，重启续采优先使用冻结参数。
- 新增的 DSO-X `single_timeout_s` 属于 Runtime Settings，会随冻结配置保存。

状态：**COMPLETE，待最终 Recipe 小批量快速回归**。

## F. 异常恢复 / 安全退出

既有 Phase 8D 能力继续有效：

- 仪表通信断开时有界重连。
- Trigger Timeout 不误判为断线。
- 最大重试耗尽后明确 FAILED，不无限循环。
- GUI 关闭使用协作式停止，不使用 `QThread.terminate()`。
- 退出后未完成 Batch 可恢复。

状态：**COMPLETE，待最终 Recipe 快速回归**。

## G. Release / CI 门槛

正式 v1.0.0 前必须全部满足：

- [ ] 商业仓库 `pytest -q` 全绿。
- [ ] FSW ARM/read platform regression 全绿。
- [ ] DSO-X driver regression 全绿。
- [ ] DSO-X `:SINGle` 专项 platform regression 全绿。
- [ ] `phase8_preflight.py --self-check` 通过。
- [ ] Final RC GUI offscreen smoke 通过。
- [ ] PyInstaller Windows ZIP 构建通过。
- [ ] 一次完整配对一键真机采集通过：两次 DSO-X Single + EXT Single Sweep + Free Run Single Sweep。
- [ ] 一个配对 Job 的四份主数据均存在、可打开且互不覆盖。
- [ ] 固定频率小批量运行通过，并快速检查暂停/继续。
- [ ] `timing.csv` / HTML 的新节点耗时量级合理。

完成以上项目后才创建正式 `v1.0.0` Tag / GitHub Release。

## H. 不阻塞 v1.0.0

- USB→TCP Bridge 的 USB/转发器侧直接拔除恢复能力
- PDF 报告
- 更多仪表型号
- 云端报告
- 数据库索引
- 更完整的 UI 国际化

## 当前结论

Phase 8A–8D 的基础能力已经完成。Recipe 后续不再扩展功能范围；当前只处理 **Single 最终规则的 CI 收口 + 一次完整真机一键确认 + 小批量快速回归**，随后发布 v1.0.0。
