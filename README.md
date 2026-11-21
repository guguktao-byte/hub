# hub — 个人多项目中枢

统一管理：全局 agent 纪律、长期记忆（灵枢记忆根）、技能库、设备清单、项目/脚本模板。
所有开发设备 clone 本仓库，保证"同一个大脑、同一套纪律"。

## 结构

```
hub/
├── AGENTS.md        # 全局工作纪律（所有 agent 必读必守）
├── memory/          # 灵枢记忆根：global + 各项目域
├── skills/          # 技能库（SKILL.md）
├── templates/       # 新项目 / 新脚本脚手架
├── devices.md       # 设备清单
├── bootstrap.ps1    # 新设备一条命令初始化（Windows 通用）
└── bootstrap/       # 灵枢(dsh-memory) 一键接入 DSH（Windows/macOS 通用）
```

## 日常循环

```bash
git pull --rebase        # 任何设备开工前
# ...干活...
git add -A && git commit -m "<模块>: <做了什么>"
git push                 # 收工前
```

## 新设备接入

Windows：
```powershell
git clone git@github.com:guguktao-byte/hub.git D:\pythonProject\hub
cd D:\pythonProject\hub
.\bootstrap.ps1
```

macOS：
```bash
git clone git@github.com:guguktao-byte/hub.git ~/pythonProject/hub
cd ~/pythonProject/hub
python3 bootstrap/bootstrap_lingshu.py --check   # 先体检
python3 bootstrap/bootstrap_lingshu.py           # 接入灵枢
```

## 新项目接入

1. `templates/project-AGENTS.md` 复制到新项目根，改名 `AGENTS.md`，按注释填写
2. `memory/` 下建同名域目录
3. 项目仓库推 GitHub/Gitee，并把地址登记进 `devices.md` 的仓库清单
