# 设备清单

| 设备 | 系统 | 角色 | 代码根目录 | 环境要点 |
| --- | --- | --- | --- | --- |
| gugutao-dev-workstation | Windows | 主力开发机 | D:\pythonProject | git 已配（咕咕涛 <1973226988@qq.com>）；GitHub SSH：ed25519 → ssh.github.com:443；DSH 已装 |

## 仓库清单

| 仓库 | 云端 | 本地路径 | 说明 |
| --- | --- | --- | --- |
| hub | github.com/guguktao-byte/hub | D:\pythonProject\hub | 本仓库（全局层） |
| camelot-service | gitee.com/KTtao/camelot-service | D:\pythonProject\卡密服务 | 卡密服务+破川+狂暴+罗盘工作区 |

## macOS 第二台设备接入（待执行）

1. 安装 Node.js 22+（`brew install node`）、Python 3.9+、DSH 桌面端（打开一次生成 `~/.dsh/profiles/desktop`）。
2. `git clone git@github.com:guguktao-byte/hub.git ~/pythonProject/hub`，项目仓同样 clone 到 `~/pythonProject/`。
3. `cd ~/pythonProject/hub && python3 bootstrap/bootstrap_lingshu.py --check` 体检（node/npm/python/profile 是否齐备）。
4. 体检通过后 `python3 bootstrap/bootstrap_lingshu.py` 正式接入（自动签发本机令牌、装插件、写配置）。
5. 完全退出并重开 DSH → 新会话确认出现 cg / stg。
6. 注意：Finder/Dock 启动的 GUI 不读 shell 环境，脚本会把令牌明文写进 profile 的 `cordis.patch.yml`（本地文件，不入库）；令牌库在各机 `~/.mdcg/_tokens.json`。
