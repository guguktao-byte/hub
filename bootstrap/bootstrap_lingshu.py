#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢(dsh-memory) 一键接入 DSH desktop profile —— 跨平台 (Windows / macOS / Linux)

为什么需要这个脚本：
  1) DSH 桌面端只允许 Electron 管理 desktop profile，官方 dsh plugin --profile desktop add
     会被拒绝（profile is managed exclusively by the Electron application）。
  2) 手工 pnpm add 在部分机器会撞 pnpm store 版本不一致（ERR_PNPM_UNEXPECTED_STORE）。
  所以这里用「npm pack 下载 -> 解包进 profile/node_modules -> 在插件目录内 npm install 运行时依赖」
  的方式安装；npm / python / tarfile 三个工具在 Windows 与 macOS 上行为一致。

幂等，可重复运行：
  - preflight：检查 node / npm / python 与 DSH profile
  - 安装插件包到 <DSH_HOME>/profiles/<profile>/node_modules/@furongjun1999/dsh-memory
  - 在插件目录内装运行时依赖（@deepseek-ai/schemastery 及其依赖），--omit=peer 不拉 DSH 框架
  - 写 profile/package.json：dependencies + dsh.profile.bundles
  - 写 profile/cordis.patch.yml：灵枢配置块（记忆根 = <hub>/memory/mdcg）
  - 签发写入令牌（designer）；Windows 走 setx + !!js 环境变量，macOS 走配置文件明文
    （Finder 启动的 GUI 拿不到 shell 环境，故 macOS 明文最稳）
  - pip 安装 zstandard（会话 .zstd 转录依赖，失败仅告警）
  - 自检：node 导入插件、md_cg --show-config、initialize 握手
最后打印「重启 DSH -> 验证 cg/stg」。

用法：
  python bootstrap/bootstrap_lingshu.py                 # 安装/修复（默认 profile=desktop）
  python bootstrap/bootstrap_lingshu.py --check         # 只体检，不改动
  python bootstrap/bootstrap_lingshu.py --dry-run       # 打印计划，不落盘
  python bootstrap/bootstrap_lingshu.py --force         # 强制重装插件包
  python bootstrap/bootstrap_lingshu.py --profile desktop --hub /path/to/hub --version 0.11.1
  # 隔离测试：--dsh-home <临时目录>，并设 MDCG_AUX_ROOT 隔离令牌库
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PKG = "@furongjun1999/dsh-memory"
DEFAULT_VERSION = "0.11.1"
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PLUGIN_REL = Path("node_modules") / "@furongjun1999" / "dsh-memory"


def log(msg=""):
    print(msg, flush=True)


def step(n, msg):
    log("\n[" + str(n) + "] " + msg)


def die(msg, code=2):
    log("✗ " + msg)
    sys.exit(code)


def npm_cmd():
    for c in ("npm.cmd", "npm"):
        p = shutil.which(c)
        if p:
            return p
    return "npm.cmd" if IS_WIN else "npm"


def node_cmd():
    return shutil.which("node") or "node"


def run(cmd, cwd=None, env=None, check=True, timeout=600):
    e = dict(os.environ)
    if env:
        e.update(env)
    log("  $ " + " ".join(str(c) for c in cmd) + (("  (cwd=" + str(cwd) + ")") if cwd else ""))
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=e,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except Exception as ex:  # noqa: BLE001
        if check:
            die("命令无法执行：" + " ".join(cmd) + "（" + str(ex) + "）")
        return 1, "", str(ex)
    if p.stdout.strip():
        log(p.stdout.strip()[-1500:])
    if p.returncode != 0:
        if p.stderr.strip():
            log("  [stderr] " + p.stderr.strip()[-1500:])
        if check:
            die("命令失败（exit=" + str(p.returncode) + "）：" + " ".join(cmd))
    return p.returncode, p.stdout, p.stderr


def dsh_home(args):
    if args.dsh_home:
        return Path(args.dsh_home).expanduser().resolve()
    if os.environ.get("DSH_HOME"):
        return Path(os.environ["DSH_HOME"]).expanduser().resolve()
    return Path.home() / ".dsh"


def can_import_plugin(plugin_dir):
    entry = plugin_dir / "lib" / "index.js"
    if not entry.exists():
        return False
    uri = entry.as_uri()
    code = "import(" + json.dumps(uri) + ").then(m=>{console.log('IMPORT_OK',Object.keys(m).join(','));}).catch(e=>{console.error('IMPORT_FAIL',e&&e.message);process.exit(1);})"
    rc, out, err = run([node_cmd(), "-e", code], check=False, timeout=60)
    ok = rc == 0 and "IMPORT_OK" in out
    if not ok and err.strip():
        log("  [导入失败] " + err.strip()[-400:])
    return ok


def preflight(profile_dir):
    problems = []
    if shutil.which("node") is None:
        problems.append("未找到 node（请先装 Node.js 22+）")
    if shutil.which(npm_cmd()) is None:
        problems.append("未找到 npm")
    if sys.version_info < (3, 9):
        problems.append("Python 版本过低（需 3.9+）")
    if not profile_dir.exists():
        problems.append("DSH profile 目录不存在：" + str(profile_dir) + "（先在 DSH 桌面端里打开过一次）")
    log("  平台：" + platform.platform() + " | Python：" + sys.version.split()[0])
    log("  profile：" + str(profile_dir))
    log("  node：" + str(shutil.which("node")) + " | npm：" + npm_cmd())
    if problems:
        for p in problems:
            log("  ⚠ " + p)
        die("preflight 未通过")
    log("  ✓ preflight 通过")


def install_plugin(plugin_dir, version, force, dry):
    already = can_import_plugin(plugin_dir)
    if already and not force:
        log("  插件已存在且可导入，跳过安装（--force 可强制重装）")
        return
    if dry:
        log("  [dry-run] 将 npm pack " + PKG + "@" + version + " 并解包到 " + str(plugin_dir) + "，随后在插件目录 npm install 运行时依赖")
        return
    tmp = Path(tempfile.mkdtemp(prefix="lingshu-"))
    try:
        run([npm_cmd(), "pack", PKG + "@" + version], cwd=tmp)
        tgzs = sorted(tmp.glob("*.tgz"))
        if not tgzs:
            die("npm pack 未产出 tgz")
        extract_dir = tmp / "pkg"
        extract_dir.mkdir()
        with tarfile.open(tgzs[0]) as tf:
            try:
                tf.extractall(extract_dir, filter="data")  # py3.12+ 安全解包
            except TypeError:
                tf.extractall(extract_dir)
        src = extract_dir / "package"
        if not (src / "package.json").exists():
            die("解包结构异常：未找到 package/package.json")
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        plugin_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, plugin_dir)
        log("  已落位：" + str(plugin_dir))
        run([npm_cmd(), "install", "--omit=peer", "--ignore-scripts",
             "--no-package-lock", "--no-audit", "--no-fund"], cwd=plugin_dir, timeout=900)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not can_import_plugin(plugin_dir):
        die("插件安装后仍无法导入（缺依赖？）")


def ensure_package_json(profile_dir, version, dry):
    pj_path = profile_dir / "package.json"
    if not pj_path.exists():
        die("找不到 " + str(pj_path) + "（profile 结构异常）")
    data = json.loads(pj_path.read_text(encoding="utf-8-sig"))
    data.setdefault("dependencies", {})[PKG] = version
    prof = data.setdefault("dsh", {}).setdefault("profile", {})
    bundles = prof.setdefault("bundles", [])
    added = PKG not in bundles
    if added:
        bundles.append(PKG)
    if dry:
        log("  [dry-run] package.json：dependency=" + version + "，bundles " + ("将追加" if added else "已含"))
        return
    pj_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("  ✓ package.json 已更新（dependencies + bundles）")


def patch_block(memory_root, python_exe, token_line):
    root = memory_root.as_posix()
    py = Path(python_exe).as_posix()
    return (
        "\n# ==== 灵枢（dsh-memory）· 长期记忆与认知图（bootstrap 生成，可重复运行）====\n"
        "# 记忆真源：<hub>/memory/mdcg；凭据见下方 env.MDCG_TOKEN\n"
        "- id: furongjun1999-dsh-memory\n"
        "  config:\n"
        '    serverName: "lingshu"\n'
        '    python: "' + py + '"\n'
        '    identity: "灵枢"\n'
        '    tools: "core"\n'
        '    moduleArgs: [ "-m", "md_cg.mcp_server" ]\n'
        "    memory:\n"
        "      userMessage: true\n"
        "      assistantMessage: false\n"
        "      toolResult: false\n"
        "      importance: 0.6\n"
        "    env:\n"
        "      " + token_line + "\n"
        '      MDCG_WRITE_GATE: "warn"\n'
        "    toolCallTimeoutMs: 60000\n"
        "    maxRetryDelayMs: 30000\n"
        "    failOnStartupError: false\n"
        "    mdcg:\n"
        "      enabled: true\n"
        '      root: "' + root + '"\n'
        '      actor: "dsh-memory"\n'
        '      tenant: "default"\n'
        '      clearance: "private"\n'
    )


def ensure_patch(profile_dir, memory_root, python_exe, token_line, dry):
    p = profile_dir / "cordis.patch.yml"
    text = p.read_text(encoding="utf-8-sig") if p.exists() else ""
    if "- id: furongjun1999-dsh-memory" in text:
        log("  cordis.patch.yml 已存在灵枢配置块，跳过（如需重建请手删该块）")
        return
    block = patch_block(memory_root, python_exe, token_line)
    if dry:
        log("  [dry-run] 将向 cordis.patch.yml 追加灵枢配置块（root=" + memory_root.as_posix() + "）")
        return
    if not text.endswith("\n"):
        text += "\n"
    p.write_text(text + block, encoding="utf-8")
    log("  ✓ cordis.patch.yml 已追加灵枢配置块")


def read_existing(profile_dir):
    """返回 (是否有灵枢块, 令牌模式 literal|env|None, 令牌值|None)。用于幂等：已配置则不重签。"""
    p = profile_dir / "cordis.patch.yml"
    if not p.exists():
        return False, None, None
    text = p.read_text(encoding="utf-8-sig")
    has_block = "- id: furongjun1999-dsh-memory" in text
    val = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("MDCG_TOKEN:"):
            val = s.split(":", 1)[1].strip().strip('"').strip("'")
            break
    if val and val.startswith("mdcg1."):
        return has_block, "literal", val
    if val and "process.env.MDCG_TOKEN" in val:
        return has_block, "env", os.environ.get("MDCG_TOKEN")
    return has_block, None, None


def issue_token(plugin_dir, memory_root):
    env = {
        "PYTHONPATH": str(plugin_dir),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "MDCG_ROOT": str(memory_root),
        "MDCG_ALLOW_ROOT_ISSUE": "1",
    }
    rc, out, err = run([sys.executable, "-m", "md_cg.tokens", "issue",
                        "--role", "designer", "--actor", "dsh-memory",
                        "--clearance", "private"], env=env, check=False, timeout=120)
    combined = (out or "") + "\n" + (err or "")
    dec = json.JSONDecoder()
    i = combined.find("{")
    while i != -1:
        try:
            obj, _end = dec.raw_decode(combined[i:])
            if isinstance(obj, dict) and obj.get("token"):
                return obj["token"]
        except Exception:
            pass
        i = combined.find("{", i + 1)
    die("令牌签发失败，未解析到 token：\n" + combined[-1200:])


def persist_token(token):
    if IS_WIN:
        run(["setx", "MDCG_TOKEN", token], check=False)
        log("  ✓ 已 setx MDCG_TOKEN（Windows 用户环境变量；新进程生效）")
        return 'MDCG_TOKEN: !!js process.env.MDCG_TOKEN'
    write_shell_rc(token)
    log("  ✓ 令牌写入 profile 配置（明文，本地文件，不入库）；并写入 shell rc 便于终端启动")
    return 'MDCG_TOKEN: "' + token + '"'


def write_shell_rc(token):
    rc = Path.home() / (".zshrc" if IS_MAC else ".bashrc")
    begin, end = "# >>> lingshu:MDCG_TOKEN >>>", "# <<< lingshu:MDCG_TOKEN <<<"
    block = begin + "\nexport MDCG_TOKEN=\"" + token + "\"\n" + end + "\n"
    old = rc.read_text(encoding="utf-8") if rc.exists() else ""
    if begin in old and end in old:
        head, rest = old.split(begin, 1)
        _, tail = rest.split(end, 1)
        new = head + block + tail
    else:
        new = old + ("\n" if old and not old.endswith("\n") else "") + block
    rc.write_text(new, encoding="utf-8")


def ensure_zstandard(dry):
    rc, _, _ = run([sys.executable, "-c", "import zstandard"], check=False, timeout=60)
    if rc == 0:
        log("  zstandard 已安装")
        return
    if dry:
        log("  [dry-run] 将 pip install zstandard")
        return
    run([sys.executable, "-m", "pip", "install", "zstandard"], check=False, timeout=600)
    rc3, _, _ = run([sys.executable, "-c", "import zstandard"], check=False, timeout=60)
    if rc3 == 0:
        log("  ✓ zstandard 安装成功")
    else:
        log("  ⚠ zstandard 未装上（自动记忆会话转录会受限，不影响核心读写）。可手动：" + sys.executable + " -m pip install --user zstandard")


def validate(plugin_dir, memory_root, token, dry):
    if dry:
        log("  [dry-run] 跳过自检")
        return
    env = {
        "PYTHONPATH": str(plugin_dir),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "MDCG_ROOT": str(memory_root),
        "MDCG_TOKEN": token,
        "MDCG_ACTOR": "dsh-memory",
        "MDCG_TENANT": "default",
        "MDCG_CLEARANCE": "private",
        "MDCG_HARNESS": "dsh",
        "MDCG_UNIT": "agent",
    }
    run([sys.executable, "-m", "md_cg.mcp_server", "--show-config"], env=env, check=False, timeout=120)
    try:
        init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "bootstrap", "version": "0"}}}) + "\n"
        p = subprocess.run([sys.executable, "-m", "md_cg.mcp_server"], env={**os.environ, **env},
                           input=init, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        first = (p.stdout or "").splitlines()[0] if p.stdout else ""
        obj = json.loads(first) if first.strip().startswith("{") else {}
        info = (obj.get("result") or {}).get("serverInfo")
        if info:
            log("  ✓ initialize 应答：" + str(info.get("name")) + " " + str(info.get("version")))
        else:
            log("  ⚠ initialize 未返回 serverInfo：" + (p.stderr or "")[-300:])
    except Exception as ex:  # noqa: BLE001
        log("  ⚠ initialize 握手异常：" + str(ex))


def main():
    ap = argparse.ArgumentParser(description="灵枢(dsh-memory) 一键接入 DSH profile（跨平台）")
    ap.add_argument("--profile", default="desktop")
    ap.add_argument("--dsh-home", default=None, help="覆盖 DSH_HOME（默认 ~/.dsh）")
    ap.add_argument("--hub", default=None, help="hub 仓库根（默认本脚本所在仓库；记忆根=<hub>/memory/mdcg）")
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--force", action="store_true", help="强制重装插件包")
    ap.add_argument("--check", action="store_true", help="只体检不改动")
    ap.add_argument("--dry-run", action="store_true", help="打印计划不落盘")
    ap.add_argument("--no-zstandard", action="store_true")
    ap.add_argument("--simulate-os", choices=["windows", "macos", "linux"], default=None,
                    help=argparse.SUPPRESS)  # 仅供在 Windows 上验证 macOS 分支
    args = ap.parse_args()
    if args.simulate_os:
        global IS_WIN, IS_MAC
        IS_WIN = args.simulate_os == "windows"
        IS_MAC = args.simulate_os == "macos"

    hub = Path(args.hub).expanduser().resolve() if args.hub else REPO_ROOT
    memory_root = hub / "memory" / "mdcg"
    profile_dir = dsh_home(args) / "profiles" / args.profile
    plugin_dir = profile_dir / PLUGIN_REL
    dry = args.dry_run or args.check
    python_exe = sys.executable

    log("=" * 60)
    log("灵枢 接入 DSH —— profile=" + args.profile + " | " + ("检查" if args.check else ("dry-run" if args.dry_run else "安装/修复")))
    log("hub=" + str(hub))
    log("memory_root=" + str(memory_root))
    log("plugin_dir=" + str(plugin_dir))
    log("=" * 60)

    step(1, "preflight")
    preflight(profile_dir)

    if args.check:
        log("\n[体检结果]")
        log("  插件可导入：" + str(can_import_plugin(plugin_dir)))
        pj = profile_dir / "package.json"
        if pj.exists():
            d = json.loads(pj.read_text(encoding="utf-8-sig"))
            log("  package.json 已声明：dep=" + str(PKG in d.get("dependencies", {})) + " / bundles=" + str(PKG in d.get("dsh", {}).get("profile", {}).get("bundles", [])))
        pt = profile_dir / "cordis.patch.yml"
        log("  patch 含灵枢块：" + str(pt.exists() and "- id: furongjun1999-dsh-memory" in pt.read_text(encoding="utf-8-sig")))
        log("  记忆库目录存在：" + str(memory_root.exists()))
        return

    step(2, "安装插件包")
    install_plugin(plugin_dir, args.version, args.force, args.dry_run)

    step(3, "更新 profile/package.json")
    ensure_package_json(profile_dir, args.version, args.dry_run)

    step(4, "准备写入令牌")
    has_block, tok_mode, tok_val = read_existing(profile_dir)
    if has_block:
        token = tok_val or os.environ.get("MDCG_TOKEN")
        token_line = None  # 已有配置，不重写、不重签
        if token:
            log("  复用已有配置令牌（不重签）")
        else:
            log("  ⚠ 已有配置但当前 shell 未取到令牌值；跳过签发，自检降级")
    elif args.dry_run:
        log("  [dry-run] 将签发 designer 令牌")
        token = None
        token_line = 'MDCG_TOKEN: !!js process.env.MDCG_TOKEN' if IS_WIN else 'MDCG_TOKEN: "DRYRUN"'
    else:
        memory_root.mkdir(parents=True, exist_ok=True)
        token = issue_token(plugin_dir, memory_root)
        log("  ✓ 令牌已签发：" + token[:24] + "...")
        token_line = persist_token(token)

    step(5, "写 cordis.patch.yml 灵枢配置块")
    ensure_patch(profile_dir, memory_root, python_exe, token_line, args.dry_run)

    step(6, "会话转录依赖 zstandard")
    if args.no_zstandard:
        log("  跳过（--no-zstandard）")
    else:
        ensure_zstandard(args.dry_run)

    step(7, "自检")
    if not args.dry_run:
        if not can_import_plugin(plugin_dir):
            die("插件最终导入失败")
        log("  ✓ 插件导入通过")
    validate(plugin_dir, memory_root, token or "", args.dry_run)

    log("\n" + "=" * 60)
    log("完成。最后一步：完全退出 DSH 桌面端再重新打开（新增 bundle 与环境变量需新进程生效）。")
    log("重启后在新会话确认：出现 cg / stg 工具；cg(op=status) 显示 root=" + memory_root.as_posix())
    log("=" * 60)


if __name__ == "__main__":
    main()
