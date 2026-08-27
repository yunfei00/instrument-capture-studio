# Phase 8 最终对齐与验收清单

目标：在 v1.0.0 发布前先把真实采集业务语义对齐，再完成异常恢复、数据完整性和 Windows 发布验收。

状态定义：

- PASS：已经通过
- PENDING：需要实现或补验
- OPTIONAL：不阻塞 v1.0.0

## A. 已通过的基线

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| FSW 真机连接与身份识别 | PASS | 已验证 |
| DSO-X 真机连接与身份识别 | PASS | 已验证 |
| 单次双仪表联合采集 | PASS | GUI 真机通过 |
| 6 个标准 Job 文件 | PASS | 真机确认完整生成 |
| FSW bounded timeout | PASS | 真机验证 |
| FSW 运行中取消 / ABORt | PASS | 真机验证 |
| 频率循环批量采集 | PASS | 700–800 MHz / 5 MHz / 21 点 |
| 大规模稳定采集 | PASS | 每频点 100 次，共 2100 次完成 |
| 参数自动保存 / 恢复 | PASS | 用户验收 |
| 配置模板 | PASS | 用户验收 |
| Spectrum / Waveform 曲线预览 | PASS | 用户验收 |
| Batch HTML 报告 / jobs.csv | PASS | 用户验收 |
| 全量曲线导出 | PASS | 用户验收 |
| 固定频率连续采集 | PASS | 用户验收 |
| Windows GUI 打包 | PASS | CI PyInstaller 通过 |
| Batch 数据完整性 preflight | PASS | 真实 Batch 验收通过 |
| 主动停止采集 | PASS | CANCELED 后可再次正常采集 |

## B. v1.0 强制功能对齐：采集 Recipe

当前 GUI 的“单次 / 扫频 / 固定连续”描述的是运行策略，不应该再和“采什么数据”混在一起。v1.0 改成两个维度：

1. **采集内容 Recipe**
   - `EXT 联合 + IMM 配对样本`
   - `IMM 频谱单采`
   - `DSO-X 示波器单采`
2. **运行策略**
   - 单次
   - 频率循环
   - 固定频率重复

### B1. EXT 联合 + IMM 配对样本

每个逻辑样本建议按以下顺序执行：

1. 配置 FSW 当前中心频率 / Span / RBW / VBW。
2. FSW 切换为 EXT，并先进入单次采集等待状态。
3. 执行 DSO-X 采集，使硬件连接产生 EXT 触发。
4. FSW 等待完成并读取 EXT Spectrum。
5. FSW 切换为 IMM。
6. 再采一份 IMM Spectrum，作为同一逻辑样本的配对训练数据。
7. 保存 DSO-X + EXT Spectrum + IMM Spectrum + metadata。

注意：FSW 必须先 ARM 再让示波器侧产生触发，不能等示波器事件已经结束后才启动 FSW，否则可能错过 EXT 触发。

状态：PENDING

### B2. IMM 频谱单采

只连接/使用 FSW：

1. Trigger = IMM。
2. 采一份 Spectrum。
3. 不要求 DSO-X 在线。

支持单次、扫频和固定频率重复。

状态：PENDING

### B3. DSO-X 示波器单采

只连接/使用 DSO-X，不要求 FSW 在线。

- Waveform Channel 必须在 GUI 明确可选。
- 首次默认 Channel 1。
- 后续保存用户上次选择。
- 运行策略至少支持单次和固定次数重复。

状态：PENDING

## C. v1.0 强制功能对齐：暂停与断点续采

### C1. 暂停 / 继续

新增“暂停采集”按钮。

- 暂停发生在一个逻辑样本的安全边界，不在文件写到一半时硬停。
- 已完成样本不重复。
- GUI 显示 `PAUSED`。
- 点击继续后从下一个未完成逻辑样本继续。

状态：PENDING

### C2. 停止后继续

主动停止仍释放仪表会话，但 Batch 保留可恢复游标：

- 当前频率索引
- 当前重复次数
- 已完成逻辑样本数
- 未完成逻辑样本

再次点击“继续上次任务”时重新连接仪表，从下一个未完成逻辑样本继续。

状态：PENDING

### C3. 意外退出后恢复

启动 GUI 时扫描未完成 Batch。对于上次处于 `RUNNING / PAUSED / CANCELED` 且未完成的任务，提供“继续上次任务”。

如果程序在一个逻辑样本中途退出，该样本按未完成处理；恢复时重新执行整个逻辑样本，保证 EXT / IMM / DSO-X 配对一致，不拼接半个旧样本和半个新样本。

状态：PENDING

## D. v1.0 强制功能对齐：节点耗时

每个采集节点记录：

- `started_at`
- `finished_at`
- `duration_ms`
- 状态
- 错误（如有）

至少覆盖：

- FSW 配置
- FSW EXT ARM
- DSO-X 采集
- FSW EXT wait/read
- FSW IMM 配置/采集
- DELAY / CYCLE_COUNT / Waveform（适用时）
- Save Result
- Job 总耗时

Batch 汇总后可计算各节点平均值、P95、最大值，用于后续性能和稳定性分析。

状态：PENDING

## E. 强制补验：FSW 物理断线恢复

开始小规模 Batch，在 FSW 节点拔掉 FSW 网线，在最大重试次数耗尽前插回。

期望：当前失败样本/Job 有记录；旧 VISA 会话释放；重新建立会话；当前逻辑样本重新执行；Batch 继续。

状态：PENDING

## F. 强制补验：DSO-X 物理断线恢复

在包含 DSO-X 的 Recipe 中断开 DSO-X 网络，期望与 E 相同。

状态：PENDING

## G. 强制补验：最大重试失败

断开一台仪表后保持断开，不在最大尝试次数内恢复。

期望：明确 FAILED；不无限重试；GUI 恢复为可操作；日志、Batch Manifest 和失败记录保留最后错误。

状态：PENDING

## H. 强制补验：Trigger Timeout 不误重连

使用 EXT Recipe 并故意不给外部触发。

期望：出现 Trigger Timeout；不进入 `RECONNECTING`；FSW 安全 ABORt；任务按测量超时处理。

状态：PENDING

## I. 强制补验：关闭 GUI 时安全退出

采集中关闭主窗口。

期望：请求安全停止；不留下后台线程继续操作仪表；再次启动时可以识别未完成任务并继续。

状态：PENDING

## J. Windows Release Candidate

正式 v1.0.0 前至少确认：

1. `pytest -q` 通过。
2. `python scripts\phase8_preflight.py --self-check` 通过。
3. GitHub Actions Product GUI smoke test 通过。
4. PyInstaller ZIP 构建通过。
5. Windows EXE 能启动。
6. EXE 下各 Recipe 所需仪表“测试连接”成功。
7. EXE 下三种 Recipe 至少各做一次小规模真机验收。
8. 暂停/继续、停止后继续、异常退出恢复完成验收。

状态：PENDING

## K. OPTIONAL，不阻塞 v1.0.0

- PDF 报告
- 更多仪表型号
- 云端报告
- 数据库索引
- UI 主题 / 国际化进一步优化

## 新 Phase 8 顺序

- **8A：真实采集 Recipe 与数据 Schema v2**
- **8B：暂停 / 停止后继续 / 意外退出恢复**
- **8C：节点耗时与性能统计**
- **8D：断线 / Timeout / GUI 退出等异常验收**
- **8E：RC EXE 与 v1.0.0 Release**

Phase 7 保持 COMPLETE，不重新打开。以上都是在真实硬件使用中发现的 v1.0 发布前业务对齐项，统一纳入 Phase 8。
