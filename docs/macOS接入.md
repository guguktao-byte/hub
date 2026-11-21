# macOS 设备接入与同步（agent 必读）

> 目标：任何 agent 在一台 macOS 设备上 clone hub 后，照本文件即可把环境、灵枢记忆、项目仓库跑起来，并与其它设备保持同步。

## 0. 适用前提

- macOS 已安装 **DSH 桌面端**，并至少打开过一次（生成 `~/.dsh/profiles/desktop`）。
- 已安装 **Node.js 22+**（含 npm）、**Python 3.9+**（`python3`）。
- 具备 hub 与项目仓库的访问权限（GitHub SSH key / Gitee 凭据）。

## 1. 首次接入（一次性）

```bash
# 1) 拉取 hub
mkdir -p ~/pythonProject
git clone git@github.com:guguktao-byte/hub.git ~/pythonProject/hub
cd ~/pythonProject/hub

# 2) 体检（不落盘）：node / npm / python / profile 是否齐备
python3 bootstrap/bootstrap_lingshu.py --check

# 3) 正式接入灵枢（装插件、签发本机令牌、写配置、装 zstandard）
python3 bootstrap/bootstrap_lingshu.py

# 4) 拉取项目仓库（按 devices.md 的仓库清单；示例为卡密服务）
git clone git@gitee.com:KTtao/camelot-service.git ~/pythonProject/卡密服务
```

接入后**必须**：完全退出 DSH 桌面端 → 重新打开（新增 bundle 与环境变量需新进程生效）。
验收：新会话工具出现 **cg / stg**；`cg(op="status")` 的 `root` = `<hub>/memory/mdcg`。

## 2. macOS 专属注意事项

- **令牌**：Finder / Dock 启动的 GUI 不读 shell 环境，bootstrap 会把 `MDCG_TOKEN` **明文写进 `~/.dsh/profiles/desktop/cordis.patch.yml`**（本地文件、不入库），并写一份到 `~/.zshrc`。令牌库在 `~/.mdcg/_tokens.json`，每台设备各自签发、不入库。
- **解释器**：bootstrap 用 `python3` 的绝对路径写入配置；若 `pip` 报 externally-managed，用 `python3 -m pip install --user zstandard`（zstandard 缺失只影响会话转录，不影响记忆读写）。
- **profile 名**：默认 `desktop`；若不同，加 `--profile <名>`。
- **Node/npm 必须在 PATH**（`brew install node`）。

## 3. 日常同步循环（agent 必须遵守）

开工前，每个仓库先拉：
```bash
cd ~/pythonProject/hub && git pull --rebase
cd ~/pythonProject/卡密服务 && git pull --rebase   # 对应项目仓库
```

改动后（**先给人看 diff，人确认后再提交**）：
```bash
git add -A && git status --short          # 核对；严禁提交密钥/token/.env/*.db
git commit -m "<模块/项目名>: <做了什么>"
git push
```

- 提交前必须 `git status` 核对；`.gitignore` 已排除灵枢运行时（锁/索引/审计/`_keys.json`）。
- 用户说「同步」= 本地提交 + 推送云端；用户没说不要擅自 push。
- 冲突由 agent 合并，合并结果以 diff 交人确认。

## 4. 记忆同步

- 灵枢记忆真源 = `<hub>/memory/mdcg`（纯文本 md 节点，随 hub 同步）。
- `*.md` 记忆节点入库；`_keys.json`/锁/索引/审计 已被 gitignore，不入库。
- 默认只写 internal / knowledge / contextual；若要写 `private` 密级节点，`_keys.json` 需另行安全同步。

## 5. 常见问题

| 现象 | 处理 |
| --- | --- |
| `--check` 报 npm 不存在 | `brew install node` |
| pip 报 externally-managed | `python3 -m pip install --user zstandard` |
| profile 目录不存在 | 先打开一次 DSH 桌面端 |
| cg / stg 不出现 | 看 DSH 启动日志里含 `dsh-memory` / `mdcg` 的行；先跑 `--check` |
| 换了设备记忆没更新 | 先 `git pull --rebase` hub |

## 6. 给 agent 的执行清单（照做即可）

1. `cd ~/pythonProject/hub && git pull --rebase`
2. `python3 bootstrap/bootstrap_lingshu.py --check`（按提示补齐 node/python/profile）
3. `python3 bootstrap/bootstrap_lingshu.py`（正式接入）
4. 提示用户 **完全退出并重开 DSH**
5. 验收：新会话出现 cg/stg、`cg(op="status")` 的 root 正确
6. 改代码：先 `git pull --rebase` 项目仓 → 改 → 给人看 diff → 等用户说「同步」再 commit+push
