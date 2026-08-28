# Paired Recipe Realignment

状态：**真机单步验证中，正式 Workflow / Schema 尚未切换。**

本轮需求调整的是正式联合采集的核心硬件时序，因此 v1.0.0 Release 暂停。Phase 8B 的暂停/续采、Phase 8D 的断线恢复/Timeout/安全退出等基础能力继续保留，等新 Recipe 合成后做快速回归。

## 1. FSW 配置边界

正式测试前由测试人员在 FSW 前面板准备好当前测量，包括中心频率、Span、RBW、VBW、Sweep Time 等。

新 Recipe **不得在每个逻辑样本开始时重新覆盖这些频谱参数**。工具只：

1. 读取当前 `SENSe:SWEep:TIME?`。
2. 在需要同步采集时切换 Trigger 为 `EXT` 并 ARM。
3. 在最后一份频谱采集前切换 Trigger 为 Free Run / `IMM`。

## 2. 新正式硬件时序

设读取到的 FSW Sweep Time 为 `T`。

1. 读取 FSW Sweep Time：`SENSe:SWEep:TIME?`。
2. 配置 DSO-X 第一次同步窗口：
   - `:TIMebase:MODE MAIN`
   - `:TIMebase:REFerence CENTer`
   - `:TIMebase:POSition T/2`
   - `:TIMebase:SCALe T/10`
   - 四项均 Query 回读确认。
3. FSW Trigger → `EXT`，然后 ARM。
4. DSO-X 第一次独立 `DIGitize` 并读取 Waveform；该硬件事件用于触发 FSW EXT。
5. 等待并读取本次 FSW EXT Spectrum。
6. 配置 DSO-X 第二次窗口：
   - Horizontal Position：GUI 可配置，当前默认 `484 ms` (`0.484 s`)
   - Horizontal Scale：GUI 可配置，当前默认 `20 ns/div` (`20e-9 s/div`)
   - 同样 Query 回读确认真实仪表接受值。
7. DSO-X 第二次独立 `DIGitize` 并读取第二份 Waveform。
8. FSW Trigger → Free Run / `IMM`，再采一份 Spectrum。
9. 上述四份数据组成一个完整逻辑样本并保存。

## 3. 单步真机验证

在正式 Workflow 合成前，GUI 增加“工程调试 / 单步采集”。调试会话保持同一对 VISA Session，不允许在 FSW ARM 与 DSO-X 触发之间重新连接。

状态机：

```text
IDLE
→ CONNECTED
→ SWEEP_TIME_READ
→ SYNC_SCOPE_CONFIGURED
→ FSW_ARMED
→ SYNC_SCOPE_CAPTURED
→ EXT_SPECTRUM_READ
→ FOLLOWUP_SCOPE_CONFIGURED
→ FOLLOWUP_SCOPE_CAPTURED
→ COMPLETE
```

GUI 单步按钮：

1. 读取 FSW Sweep Time
2. 配置示波器第一次时间窗口
3. FSW 设置 EXT 并 ARM
4. 示波器第一次采集 / 触发 FSW
5. 读取 FSW EXT 频谱
6. 配置示波器第二次时间窗口
7. 示波器第二次独立采集
8. FSW Free Run 再采一次频谱

每一步显示 SCPI、计算值、Query 回读值、数据点数、PASS / FAIL。调试窗口关闭前执行 FSW `ABORt`、恢复 `IMM`、DSO-X `STOP` 并释放会话。

## 4. 已确认可复用的 platform 能力

FSW platform Driver 已有：

- `get_sweep_time()` → `SENSe:SWEep:TIME?`
- `set_trigger_source()`
- `arm_trace_ascii()`
- `wait_and_read_trace_ascii()`
- `acquire_trace_ascii()`
- bounded timeout / `ABORt`

DSO-X platform Driver 已有：

- `get/set_timebase_position()` → `:TIMebase:POSition`
- `get/set_timebase_scale()` → `:TIMebase:SCALe`
- 通用 `query()/write()`，用于本轮先单步验证 `:TIMebase:MODE` / `:TIMebase:REFerence`
- `acquire_word_waveform()`
- `abort()` → `:STOP`

等 MODE / REFERENCE 真机回读确认后，再决定是否把它们提升为 platform 的显式 typed API；正式 Workflow 不直接散落裸 SCPI。

## 5. 正式数据命名（待单步全部 PASS 后切换）

建议新 Recipe 使用：

```text
spectrum_ext.csv / .npz
waveform_sync.csv / .npz
waveform_followup.csv / .npz
spectrum_freerun.csv / .npz
```

旧 `waveform_delay / waveform_cycle / spectrum_imm` 先不删除，直到新流程真机单步全部 PASS 并完成一次完整合成验证。之后一次性切换 Schema，避免调试阶段反复破坏正式数据契约。

## 6. 合成门槛

只有以下 8 个单步在真机全部 PASS 后，才修改正式 `PairedCaptureWorkflow`：

- Sweep Time 读取正确
- 第一次 Position / Scale 计算及回读正确
- FSW EXT ARM 正确
- 第一次 DSO-X 采集能触发并形成预期数据
- FSW EXT read 正确
- 第二次 `484 ms / 20 ns/div`（或后续确认值）设置及回读正确
- 第二次 DSO-X Waveform 正确
- FSW Free Run Spectrum 正确

随后再执行：单次完整采集 → 固定频率小批量 → 暂停/续采 → 断线/Timeout/安全关闭快速回归 → RC。
