# Instrument Capture Studio

面向实验室与研发测试场景的商业化仪表联合采集软件。

当前第一版主要支持：

- Keysight DSO-X 3034A 示波器
- Rohde & Schwarz FSW 频谱分析仪

## 项目定位

Instrument Capture Studio 负责“多仪表联合采集产品层”。

主要包括：

- 仪表连接与状态管理
- FSW + DSO-X 联合采集工作流
- 采集参数配置与模板
- 单次采集与连续采集
- DSO-X DELAY / CYCLES 测量
- 波形与频谱数据保存
- CSV / NPZ 数据导出
- 数据可视化
- 批量转图
- HTML / PDF 报告
- 日志记录
- 断线检测与自动恢复
- 商业化桌面 UI

## 与 Instrument Automation Platform 的关系

本项目不重复实现底层仪表驱动。

单仪表通信、SCPI 命令、设备兼容、Record/Replay、
实机验证等通用能力由：

`instrument-automation-platform`

负责。

本项目通过 adapters 层接入这些仪表能力，并在 workflows
层实现具体的联合采集业务。

## 当前目标

第一阶段首先完成：

1. DSO-X 3034A 连接与控制
2. FSW 连接与控制
3. 联合采集工作流
4. DELAY / CYCLES 示波器采集
5. 频谱数据采集
6. 数据统一保存
7. 基础桌面 UI
8. 异常处理与断线恢复

## 当前状态

Version: 0.1.0

项目处于基础架构搭建阶段。
