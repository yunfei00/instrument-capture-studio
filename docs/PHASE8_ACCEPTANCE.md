# Phase 8 最终验收清单

目标：完成 v1.0.0 发布前的真实仪表、异常恢复、数据完整性、Windows 打包和用户流程验收。

状态定义：

- PASS：已经通过
- PENDING：需要补验
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

## B. 强制补验：安全停止

建议固定频率连续采集设置 50–100 次，开始后主动点击“停止采集”。

期望：

1. GUI 立即显示已发送停止请求。
2. 当前仪表操作在安全边界结束或 ABORt。
3. Batch / Job 状态为 CANCELED，而不是程序崩溃。
4. 两台仪表最终释放会话。
5. 软件仍可继续发起下一次采集。

状态：PENDING

## C. 强制补验：FSW 物理断线恢复

步骤：

1. 开始固定频率连续采集或小规模扫频。
2. 进入 FSW Spectrum 后拔掉 FSW 网线。
3. 等待 GUI 出现 `RECONNECTING`。
4. 在最大重试次数耗尽前插回网线。

期望：

- 当前失败 Job 保留 `job.json`。
- 旧 VISA 会话被释放。
- 2 秒后重新建立两台仪表会话。
- 使用新的 retry Job ID 重试当前采集。
- 最终 Batch 能继续执行。

状态：PENDING

## D. 强制补验：DSO-X 物理断线恢复

操作与 FSW 相同，但在 DSO-X DELAY / CYCLE_COUNT / Waveform 阶段断开 DSO-X 网络。

期望与 C 相同。

状态：PENDING

## E. 强制补验：最大重试失败

断开一台仪表后保持断开，不在 4 次尝试内恢复。

期望：

- 最终任务明确 FAILED。
- 不无限重试。
- GUI 恢复为可再次操作状态。
- 日志、失败 Job、Batch Manifest 保留最后错误。

状态：PENDING

## F. 强制补验：Trigger Timeout 不误重连

使用需要外部触发的场景并故意不给触发。

期望：

- 出现 InstrumentTimeoutError / Trigger Timeout。
- 不进入 `RECONNECTING`。
- 仪表安全 ABORt / 恢复可操作状态。

状态：PENDING（FSW bounded timeout 底层能力已真机验证，本项主要验 GUI / Batch 行为）

## G. 强制补验：关闭 GUI 时安全退出

在采集过程中关闭主窗口。

期望：

- 软件请求停止采集。
- 不留下后台线程继续操作仪表。
- 不发生未处理异常。
- 再次启动 GUI 可正常连接和采集。

状态：PENDING

## H. 数据完整性检查

对已完成的大 Batch 执行：

```powershell
python scripts\phase8_preflight.py --data-root <你的数据目录>
```

期望输出：

```text
PASS: Batch artifact acceptance
```

校验内容：

- Batch 状态 succeeded
- completed_captures == total_captures
- 成功 Job 数量与完成数量一致
- 每个成功 Job 都存在：job.json、metadata.json、spectrum.csv、spectrum.npz、waveform.csv、waveform.npz

状态：PENDING（工具已提供，等待在真实 2100 次数据目录执行）

## I. Windows Release Candidate

正式 v1.0.0 前至少确认一次：

1. `pytest -q` 通过。
2. `python scripts\phase8_preflight.py --self-check` 通过。
3. GitHub Actions Product GUI smoke test 通过。
4. PyInstaller ZIP 构建通过。
5. Windows EXE 能启动。
6. EXE 下两台仪表“测试连接”成功。
7. EXE 下执行一次完整联合采集成功。

状态：PENDING

## J. OPTIONAL，不阻塞 v1.0.0

- PDF 报告
- 更多仪表型号
- 云端报告
- 数据库索引
- 更复杂的断点续采策略
- UI 主题 / 国际化进一步优化

## v1.0.0 封板条件

B、C、D、E、F、G、H、I 全部 PASS 后：

1. 将 `pyproject.toml` 版本改为 `1.0.0`。
2. Roadmap Phase 8 标记 COMPLETE。
3. 创建 `v1.0.0` Tag。
4. GitHub Actions 自动生成 Windows Release。
