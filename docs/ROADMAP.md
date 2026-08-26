# Instrument Capture Studio Roadmap

## 目标

第一版完成 DSO-X 3034A + FSW 商业化联合采集工具。

第一版固定为 8 个 Phase，Phase 8 完成后发布 v1.0.0。

---

## Phase 1 - 项目基础架构

状态：**COMPLETE**

已完成 Python 项目结构、仓库职责边界、核心数据模型、Adapter / Workflow 接口、基础异常体系和测试框架。

---

## Phase 2 - DSO-X 3034A 接入

状态：**COMPLETE**

已完成 DSO-X 3034A 驱动接入、连接、身份识别、状态查询、DELAY、CYCLE_COUNT、Waveform 与基础错误处理，并已参与真实双仪表联合采集。

---

## Phase 3 - FSW 接入

状态：**COMPLETE**

已完成 FSW 驱动接入、连接、身份识别、状态查询、频谱配置、单次频谱采集、Trace 读取、bounded timeout、运行中取消和真机资格验证。

---

## Phase 4 - 联合采集 Workflow

状态：**COMPLETE**

完整流程：

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

已完成：

- 统一 Capture Job
- Step / Job 状态
- 超时
- 协作式取消
- 重试与失败处理
- CLI 联合采集入口
- GUI 联合采集入口
- FSW timeout 真机验证
- FSW runtime cancel 真机验证
- DSO-X 3034A 真机参与联合采集验证
- FSW + DSO-X 双仪表完整联合采集验证

2026-08-26：Windows GUI 使用默认配置完成真实 FSW + DSO-X 完整联合采集。

---

## Phase 5 - 数据管理

状态：**COMPLETE**

已完成：

- CSV / NPZ
- metadata.json
- job.json Job Manifest
- 标准目录与文件命名
- Job ID
- 仪表身份与配置快照
- Job / Step 时间与错误记录
- 成功 / 失败 / 取消持久化
- 连接阶段失败记录
- Spectrum / Waveform 重新加载
- CaptureContext 离线恢复
- CLI 真实磁盘保存
- 跨午夜 Job 单一目录
- 双仪表真机完整数据目录验证

标准 Job：

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

---

## Phase 6 - 商业桌面 UI

状态：**BASELINE COMPLETE / HARDWARE ACCEPTED**

已完成：

- Windows PySide6 GUI
- FSW / DSO-X 连接状态与连接测试
- VISA 地址和参数配置
- 开始 / 停止采集
- 实时 Capture Step 进度
- Job 状态
- 日志窗口
- 数据浏览
- Windows EXE 启动验证
- 两台仪表真机连接测试
- GUI 双仪表完整联合采集验证

结果：用户不需要操作命令行即可完成连接、采集、停止、结果保存与浏览。

---

## Phase 7 - 稳定性与产品能力

状态：**COMPLETE**

### Phase 7A - 参数持久化

状态：**COMPLETE**

- 自动保存 / 恢复 FSW VISA、Center、Span、RBW、VBW、Trigger、Timeout
- 自动保存 / 恢复 DSO-X VISA、DELAY、CYCLE_COUNT、Waveform Channel
- 自动保存 / 恢复输出目录
- 自动保存 / 恢复批量扫频参数
- 自动保存 / 恢复固定频率连续采集次数

### Phase 7B - 断线检测与自动恢复

状态：**SOFTWARE COMPLETE / PHYSICAL CABLE ACCEPTANCE IN PHASE 8**

已完成：

- InstrumentConnectionError / InstrumentCommunicationError 分类
- 当前 Job 失败信息持久化
- 释放旧 VISA / Driver / Adapter
- 默认等待 2 秒
- 创建全新会话
- 默认最多 4 次完整 Capture 尝试
- retry Job ID 不覆盖历史故障证据
- GUI `RECONNECTING` 状态
- Trigger / Measurement Timeout 不误判为掉线
- Fault Injection 验证通信异常后重连和重试
- InstrumentBusyError 独立分类，不进入自动重连

FSW / DSO-X 真实拔线、插回和最大重试失败放在 Phase 8 最终硬件验收。

### Phase 7C - 频率循环 / 批量联合采集

状态：**COMPLETE + LARGE REAL-HARDWARE RUN PASSED**

已完成：

- FrequencySweepPlan
- 起始 / 结束 / 步长 / Span / 每频点次数
- Batch Capture Runner
- Batch 内 FSW + DSO-X 长连接
- FSW 动态中心频率切换
- 每频点完整联合采集
- 每次独立 Job ID 与 6 个标准文件
- Batch ID / batch.json
- 当前频率、当前次数、总进度
- 中途安全停止
- 批量运行中连接/通信异常自动恢复
- GUI 单次 / 频率循环模式
- 批量参数自动保存 / 恢复

2026-08-26 真机大规模验证：

- 700 MHz → 800 MHz
- 步长 5 MHz
- 21 个频点
- 每频点 100 次
- 总计 2100 次完整联合采集完成

### Phase 7D - 产品增强

状态：**COMPLETE FOR v1.0.0**

已完成：

- 命名实验配置模板保存 / 加载 / 删除
- 模板保存 VISA、FSW、DSO-X、采集模式、扫频与输出目录
- 大规模 Batch / Job 摘要浏览
- GUI 限制最近 Batch / Job，避免数万文件一次性渲染
- 双击 Job 打开目录
- JSON 结构化查看器
- Spectrum / Waveform NPZ 曲线预览
- 大数组预览自动抽样
- 桌面会话日志持久化
- Batch HTML 报告
- 完整 jobs.csv
- 每频点代表性 Spectrum / Waveform SVG
- 全量 Batch Spectrum / Waveform SVG 批量导出
- 固定频率连续采集模式
- 全量转图后台执行，避免阻塞 GUI

PDF 报告不作为 v1.0.0 强制项，HTML + SVG + CSV 已满足第一版报告与可追溯需求。

Phase 7 用户功能验收已通过。

---

## Phase 8 - 验收与商业发布

状态：**IN PROGRESS**

当前版本：`0.9.0rc1`

已具备：

- 2100 次真实批量稳定采集基线
- Windows PyInstaller CI 构建
- Tag `v*` 自动创建 GitHub Release
- 产品 GUI offscreen smoke test
- Phase 8 runtime self-check
- Batch 数据完整性 preflight
- 用户指南
- Windows 部署 / 发布指南
- 最终验收清单

剩余强制验收：

1. 采集中主动停止后的安全退出与再次采集
2. FSW 真实物理断线 → 插回 → 自动恢复
3. DSO-X 真实物理断线 → 插回 → 自动恢复
4. 仪表保持断开直到最大重试次数耗尽
5. Trigger Timeout 在 GUI / Batch 层不误触发重连
6. 采集中关闭 GUI 的安全退出
7. 对真实 2100 次数据执行 `phase8_preflight.py` 并 PASS
8. 正式 Release Candidate EXE 下完成连接与一次完整联合采集

详细步骤见 `docs/PHASE8_ACCEPTANCE.md`。

全部通过后：

- 版本改为 `1.0.0`
- Phase 8 标记 COMPLETE
- 创建 `v1.0.0` Tag
- GitHub Actions 自动生成 Windows Release

---

## 第一版范围冻结

v1.0.0 核心仪表：

- Keysight DSO-X 3034A
- Rohde & Schwarz FSW

其他型号、新云服务、数据库索引、PDF 报告等不作为 v1.0.0 必须完成项。
