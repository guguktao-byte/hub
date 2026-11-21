# 灵枢（dsh-memory）一键接入 DSH —— 跨平台

把灵枢记忆插件装进 DSH 桌面端的 `desktop` profile。**Windows / macOS / Linux 同一套脚本**（Python 实现，`npm` + `python` + `tarfile` 三件跨平台工具）。

## 为什么需要它

1. DSH 桌面端只允许 Electron 管理 `desktop` profile，官方 `dsh plugin --profile desktop add` 会被拒绝（profile is managed exclusively by the Electron application）。
2. 手工 `pnpm add` 在部分机器会撞 `ERR_PNPM_UNEXPECTED_STORE`（pnpm store 版本不一致）。

所以脚本用：`npm pack 下载 -> 解包进 profile/node_modules -> 在插件目录内 npm install 运行时依赖`（`--omit=peer`，不拉 DSH 框架）。这条路在 Windows 与 macOS 上命令完全一致。

## 前置条件

- 已安装 **DSH 桌面端**，并至少打开过一次（生成 `~/.dsh/profiles/desktop`）。
- **Node.js 22+**（含 npm）、**Python 3.9+**（mac 用 `python3`）。
- 能访问 npm 镜像（默认走 registry.npmmirror.com，可用环境变量 `npm_config_registry` 覆盖）。

## 用法

Windows（PowerShell）：

```powershell
cd <你的hub仓库>
python .\bootstrap\bootstrap_lingshu.py            # 安装/修复
python .\bootstrap\bootstrap_lingshu.py --check    # 只体检
python .\bootstrap\bootstrap_lingshu.py --dry-run  # 看计划
```

macOS / Linux：

```bash
cd <你的hub仓库>
python3 bootstrap/bootstrap_lingshu.py
python3 bootstrap/bootstrap_lingshu.py --check
```

常用参数：`--profile desktop`、`--hub <hub路径>`（默认本脚本所在仓库）、`--version 0.11.1`、`--force`（强制重装插件包）、`--dsh-home <dir>`（隔离测试）。

**幂等**：重复运行会检测「插件可导入 / package.json 已声明 / patch 已含配置块 / 令牌已存在」并跳过，不会重复装、不重复签发。

## 它改了什么

| 位置 | 改动 |
|---|---|
| `<DSH_HOME>/profiles/<profile>/node_modules/@furongjun1999/dsh-memory` | 插件包 + 运行时依赖 |
| `<DSH_HOME>/profiles/<profile>/package.json` | `dependencies` + `dsh.profile.bundles` 声明该插件 |
| `<DSH_HOME>/profiles/<profile>/cordis.patch.yml` | 追加灵枢配置块（记忆根 = `<hub>/memory/mdcg`） |
| 用户环境变量 `MDCG_TOKEN` | Windows：`setx`；macOS：写入 profile 配置明文 + `~/.zshrc` |
| Python | `pip install zstandard`（会话 .zstd 转录依赖，失败仅告警） |

记忆真源固定落在 hub 仓库的 `memory/mdcg`（随 hub 多设备同步）；运行时锁/索引/审计/`_keys.json` 已被 hub `.gitignore` 排除。

## 令牌（MDCG_TOKEN）的存放差异

- **Windows**：脚本 `setx MDCG_TOKEN <token>`，配置里用 `!!js process.env.MDCG_TOKEN` 引用。新进程（重启后的 DSH）生效。
- **macOS**：从 Finder / Dock 启动的 GUI **不读 shell 环境**，所以脚本把令牌**明文写进 profile 的 cordis.patch.yml**（本地文件、不入库），同时写一份到 `~/.zshrc` 便于终端启动。若想改用 launchd 环境变量可自行改回 `!!js`。

令牌库在 `~/.mdcg/_tokens.json`（每台设备各自签发、不入库）。

## 验证（装完必做）

完整退出 DSH 桌面端 → 重新打开 → 新会话：
1. 工具里应出现 **cg / stg**；
2. `cg(op="status")` 应显示 `root=<hub>/memory/mdcg`；
3. 说一句话，`<hub>/memory/mdcg/contextual/` 下应新增 `.md`（自动记忆）。

## 常见问题

- **preflight 报 npm 不存在**：装 Node.js 22+（mac：`brew install node`）。
- **mac pip 报 externally-managed**：用 `python3 -m pip install --user zstandard` 或改用 Homebrew 的 python；zstandard 缺失只影响「会话转录」，不影响记忆读写。
- **profile 目录不存在**：先在 mac 的 DSH 桌面端打开一次。
- **cg/stg 不出现**：把 DSH 启动日志里含 `dsh-memory` / `mdcg` 的行发出来排查（多为解释器路径或依赖问题）；也可先跑 `--check`。

## 回滚

1. 从 profile `cordis.patch.yml` 删掉 `- id: furongjun1999-dsh-memory` 整块；
2. 从 profile `package.json` 的 `dependencies` 与 `dsh.profile.bundles` 删掉该包；
3. 删除 `node_modules/@furongjun1999/dsh-memory`；
4. 重启 DSH。（记忆库 `<hub>/memory/mdcg` 不动，随时可再装回来。）
