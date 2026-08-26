# Windows 部署与发布指南

## 1. 运行环境

推荐：

- Windows 10 / 11 x64
- Python 3.11（源码运行）
- NI-VISA 或可用的 PyVISA backend
- FSW 与 DSO-X 网络可达

两个仓库推荐放在同一级目录：

```text
workspace/
├── instrument-automation-platform/
└── instrument-capture-studio/
```

## 2. 源码运行

```powershell
cd instrument-automation-platform
git pull --ff-only origin main

cd ..\instrument-capture-studio
git pull --ff-only origin main
python -m pip install -e ".[gui]"
python -m pip install pyvisa pyvisa-py
python scripts\run_gui.py
```

`scripts/run_gui.py` 会寻找同级的 `instrument-automation-platform` 并加入驱动包路径。

## 3. 开发 / 发布检查

```powershell
python -m pip install -e ".[build]"
python -m pip install pytest pyvisa pyvisa-py
pytest -q
python scripts\phase8_preflight.py --self-check
```

## 4. Windows 打包

GitHub Actions 工作流：

```text
.github/workflows/windows-gui-release.yml
```

每次相关代码 push 到 `main` 会执行：

```text
pytest
→ Phase 8 self-check
→ Product GUI offscreen smoke test
→ PyInstaller
→ ZIP
→ Actions Artifact
```

Tag `v*` 时额外创建 GitHub Release 并上传 Windows ZIP。

发布包中 `BUILD.txt` 记录：产品名、版本、Git ref、commit SHA 和构建时间。

## 5. v1.0.0 发布步骤

只有 `docs/PHASE8_ACCEPTANCE.md` 的强制验收项通过后才创建正式 Tag。

```powershell
git pull --ff-only origin main
git status
pytest -q
python scripts\phase8_preflight.py --self-check

git tag -a v1.0.0 -m "Instrument Capture Studio v1.0.0"
git push origin v1.0.0
```

Tag push 后 GitHub Actions 自动构建 Release。

## 6. 公司网络无法登录 GitHub 时

公司电脑可以继续以源码方式运行，不依赖 Actions Artifact：

```powershell
git pull --ff-only origin main
python scripts\run_gui.py
```

如果公司网络允许 Git 拉取但不允许网页登录，这是首选方式。

## 7. 配置、日志与数据

- GUI 参数：Qt `QSettings` 用户级配置
- 实验模板：用户目录中的 Instrument Capture Studio 模板目录
- 会话日志：用户目录中的 Instrument Capture Studio 日志目录
- 采集数据：由 GUI“数据目录”指定

不要把真实仪表 IP、序列号或内部实验数据提交到公开仓库。

## 8. 回滚

正式版本按 Git Tag 固定。需要回滚时可检出已发布 Tag：

```powershell
git checkout v1.0.0
```

生产环境不建议直接运行未验收的任意历史 commit。
