# Kingdom Rush CE 修改器

适用于《Kingdom Rush》Steam PC 64 位 **Build 24662480** 的外置修改器。
连接用户自行启动的原版游戏，不需要分发或替换游戏文件，不是 FLiNG 官方作品。

## 下载与使用

在 [Releases](https://github.com/sdkdsd/kingdom-rush-ce-trainer/releases/latest) 下载 ZIP 并解压，运行 `KingdomRush-CE.exe`。
单文件内置本版本所需的 CE 接入组件，使用者无需另外安装 Python 或 CE。

1. 从 Steam 启动原版游戏，进入主菜单。
2. 打开修改器，点击“连接原版游戏”。
3. 选择存档，进入地图或关卡，操作对应功能。
4. 从旧版升级时先退出旧面板和游戏，再重新启动、连接。

连接和持久数据修改前会在 EXE 旁的 `backups` 目录自动备份。恢复备份必须先退出游戏。
关闭面板发送临时效果复位指令；已保存的升级、星星和解锁不会自动回滚。

## 功能

- 金币设置、增加与锁定；基地生命设置与锁定。
- 0.5–5 倍速度，火雨／援军技能冷却。
- 英雄、士兵、防御塔分别设置 0.1–100 倍伤害。
- 当前存档额外升级星星，不修改关卡星级。
- 一键解锁 13 位英雄：不伪造通关记录，标记随存档保存，连接修改器后解除选择限制。
- 当前存档 74 项成就解锁，并向当前 Steam 账户提交。

当前 Steam PC 版未启用钻石商店，因此没有钻石按钮。

**成就操作会同时解锁 Steam 成就，恢复本地存档无法撤销。**
点击按钮后，确认窗口上方会显示警告，必须完整输入 **“我确认解锁全部成就”**。
取消、输入不一致、切换存档或备份失败均不会发送命令。
“Steam 已提交”表示接口接受请求，最终同步状态请在 Steam 查看。
英雄和成就操作前，请回到地图并关闭英雄／成就窗口。

快捷键：Ctrl+F1 加金币；Ctrl+F2 生命锁定；Ctrl+F3 切换 1／2 倍速；
Ctrl+F4 冷却；Ctrl+F5 复位临时效果；F8 游戏内状态条。

## 验证状态

作者已收到使用者对原版连接、原有功能、备份恢复及新增解锁功能的实测通过反馈。
离线覆盖：173 项共享逻辑检查、117 项解锁检查、23 项面板测试，
以及 11 组真实 CE 隔离进程载荷和 6 组异常恢复场景；真实 Steam 调用不在自动测试中执行。

v2.1.0 发布保留实测通过的原始 EXE，内部标题仍显示 `2.1 RC1`。
没有为了改标题而重新构建已验收的程序。版本校验拒绝不同的游戏 EXE／DLL。
对其他游戏版本、其他电脑和全部长期游玩场景不作已测试声明。

## 源码与构建

Windows x64，Python 3.14，PyInstaller 6。自行准备合法安装的对应游戏和 CE 7.6。
设置 `KR_GAME_DIR` 为包含 `Kingdom Rush.exe` 的目录，`KR_CE_DIR` 为包含
`cheatengine-x86_64.exe`、`lua53-64.dll` 和 `defines.lua` 的 CE 目录。

```powershell
python -m pip install -r requirements-build.txt
python tools/kingdom_rush_ce/build.py
python -m PyInstaller --noconfirm --windowed --onefile --name KingdomRush-CE --distpath output/KingdomRushCE --workpath analysis/kingdom-rush/pyinstaller-ce --specpath analysis/kingdom-rush --add-data "$((Resolve-Path 'analysis/kingdom-rush/ce-stage/ce').Path);ce" analysis/kingdom-rush/ce-stage/panel.py
python tools/prepare_tests.py
python tools/run_tests.py
python tools/kingdom_rush_ce/test_release.py
```

测试准备程序仅从本机游戏提取少量原版字节码作为测试输入，保存在被 Git 忽略的 `analysis/`；
不会启动游戏。运行测试时关闭游戏，Steam 接口使用模拟对象。
`test_release.py` 需要先构建 EXE，再运行其他测试。

核心：`tools/kingdom_rush_ce/panel.py` 是界面，`bridge.lua` 是 CE 接入，
`progression.lua` 是英雄与成就功能；`tools/kingdom_rush_trainer/` 提供共享逻辑，
其中 `trainer.py` 是生成界面的基础模块，请勿把它单独作为成品运行。

## 第三方组件

Cheat Engine：https://github.com/cheat-engine/cheat-engine

发布 EXE 包含 CE 7.6 和相应运行依赖，第三方组件的权利归各自作者，
本仓库不另行授予第三方组件的许可。仓库不包含游戏本体、游戏 DLL、原版字节码、
个人存档、备份、账户凭据或测试日志。
