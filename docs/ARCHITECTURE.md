# Instrument Capture Studio Architecture

## 1. 项目定位

Instrument Capture Studio 是商业化多仪表联合采集软件。

当前首要支持：

- Keysight DSO-X 3034A
- Rohde & Schwarz FSW

本仓库负责产品层和联合采集业务，不重复开发底层仪表驱动。

## 2. 仓库边界

### instrument-automation-platform

负责单仪表能力：

- VISA / TCPIP 通信
- SCPI 命令
- 单仪表驱动
- 返回值解析
- 实机测试
- Record / Replay
- 型号和版本兼容
- 驱动级异常处理

### instrument-capture-studio

负责商业产品能力：

- 多仪表连接管理
- 多仪表状态管理
- 联合采集工作流
- 采集任务
- 配置模板
- 数据保存
- 数据浏览
- 连续采集
- 日志
- 异常恢复
- UI
- 报告

## 3. 分层

UI
↓
APP
↓
WORKFLOWS
↓
ADAPTERS + DATA
↓
instrument-automation-platform
↓
DSO-X 3034A / FSW

## 4. 目录职责

### app

负责应用启动、生命周期、任务管理和模块协调。

### core

负责数据模型、状态、枚举、公共异常和抽象接口。

### workflows

负责联合采集业务流程。

例如：

FSW Spectrum
↓
DSO-X DELAY
↓
DSO-X CYCLES
↓
Save Unified Result

具体采集顺序属于业务层，不写入单仪表 Driver。

### adapters

负责连接 instrument-automation-platform。

例如：

- FSWAdapter
- DSOX3034AAdapter

Adapter 可以调用底层 Driver，但不实现完整联合采集业务。

### data

负责：

- CSV
- NPZ
- 元数据
- 文件组织
- 批量转图
- 报告数据

### ui

负责：

- 仪表连接
- 参数配置
- 任务控制
- 状态展示
- 采集进度
- 数据浏览
- 日志
- 报告入口

UI 不直接发送 SCPI。

## 5. 核心设计原则

1. 单仪表能力与联合采集业务分离。
2. UI 不直接操作 VISA 或 SCPI。
3. 采集核心不依赖 GUI。
4. 联合采集流程放在 workflows。
5. 底层仪表接入放在 adapters。
6. 必须支持超时、取消、重试和断线恢复。
7. 每次采集必须保存完整元数据和错误信息。

## 6. 当前阶段

Version: 0.1.0

当前只建立项目架构和基础设施，暂不实现具体采集业务。
