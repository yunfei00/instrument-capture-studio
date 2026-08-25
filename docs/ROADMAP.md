# Instrument Capture Studio Roadmap

## 目标

第一版完成 DSO-X 3034A + FSW 商业化联合采集工具。

第一版固定为 8 个 Phase。

Phase 8 完成后发布 v1.0.0。

---

## Phase 1 - 项目基础架构

目标：

- 建立 Python 项目结构
- 明确仓库职责边界
- 建立核心数据模型
- 建立 Adapter 接口
- 建立 Workflow 接口
- 建立基础异常体系
- 建立测试框架

结果：

项目可以运行基础测试，但暂不连接真实仪表。

---

## Phase 2 - DSO-X 3034A 接入

目标：

- 接入 DSO-X 3034A 底层驱动
- 仪表连接
- 身份识别
- 状态查询
- DELAY 配置与采集
- CYCLES 配置与采集
- 波形读取
- 基础错误处理

结果：

可以独立完成 DSO-X 3034A 真机采集。

---

## Phase 3 - FSW 接入

目标：

- 接入 FSW 底层驱动
- 仪表连接
- 身份识别
- 状态查询
- 频谱配置
- 单次频谱采集
- Trace 数据读取
- 基础错误处理

结果：

可以独立完成 FSW 真机采集。

---

## Phase 4 - 联合采集 Workflow

状态：

**SOFTWARE COMPLETE**

已完成：

- 统一 Capture Job
- FSW Spectrum
- DSO-X DELAY
- DSO-X CYCLE_COUNT
- DSO-X Waveform
- Save Result Step
- Step 状态
- Job 状态
- 超时
- 运行中取消
- 重试
- 失败处理
- 无 GUI CLI 联合采集入口
- FSW timeout 真机验证
- FSW runtime cancel 真机验证

待硬件补充验收：

- DSO-X 3034A 真机采集
- FSW + DSO-X 双仪表完整联合采集

以上硬件待测项不阻塞 Phase 5 软件开发。

目标：

建立统一 Capture Job。

第一版支持：

FSW Spectrum
↓
DSO-X DELAY
↓
DSO-X CYCLES
↓
Save Result

同时支持：

- Step 状态
- 超时
- 取消
- 重试
- 失败处理
- Job 状态

结果：

可以无 GUI 完成一次完整联合采集。

---

## Phase 5 - 数据管理

状态：

**SOFTWARE COMPLETE**

已完成：

- CSV 保存
- NPZ 保存
- metadata.json 元数据保存
- job.json Job Manifest
- 文件命名规则
- 标准采集目录结构
- Job ID
- 仪表身份信息记录
- 仪表配置参数快照
- Job / Step 时间记录
- Job / Step 错误记录
- 成功 / 失败 / 取消状态持久化
- 连接阶段失败记录
- Spectrum / Waveform 数据重新加载
- CaptureContext 离线恢复
- CLI 真实磁盘保存入口
- 同一 Job 跨午夜保持单一目录
- 运行时 data 目录 Git 忽略规则

数据目录：

YYYY-MM-DD/
└── job_id/
    ├── job.json
    ├── metadata.json
    ├── spectrum.csv
    ├── spectrum.npz
    ├── waveform.csv
    └── waveform.npz

结果：

一次采集可以产生完整、可追踪、可重新加载的数据目录。

Phase 5 软件功能完成。

DSO-X 3034A 真机及 FSW + DSO-X 双仪表完整数据目录，
随 Phase 4 / Phase 8 的硬件验收统一补测。

---

## Phase 6 - 商业桌面 UI

目标：

使用 PySide6 建立基础商业界面。

包括：

- DSO-X 连接状态
- FSW 连接状态
- 仪表地址配置
- 参数配置
- 开始采集
- 停止采集
- 采集进度
- Job 状态
- 日志窗口
- 数据浏览

结果：

用户不需要操作命令行即可完成采集。

---

## Phase 7 - 稳定性与产品能力

目标：

- 仪表断线检测
- 自动重连
- 超时控制
- 仪表忙处理
- 用户取消
- 安全退出
- 异常恢复
- 连续采集
- 配置模板
- 数据可视化
- 批量转图
- HTML / PDF 报告

结果：

从“能用”进入“可长期运行”。

---

## Phase 8 - 验收与商业发布

目标：

- 完整实机测试
- 长时间稳定性测试
- 断网测试
- 仪表掉线测试
- 异常场景测试
- Windows 打包
- 配置目录整理
- 日志目录整理
- 用户文档
- 部署文档
- Release 构建

最终发布：

v1.0.0

---

## 第一版范围冻结

v1.0.0 核心仪表：

- Keysight DSO-X 3034A
- Rohde & Schwarz FSW

其他型号不作为 v1.0.0 必须完成项。

新增仪表型号和新增业务需求原则上进入后续版本。
