# 新设备初始化：检查基础工具 + 克隆常用仓库
Write-Host "== hub bootstrap ==" -ForegroundColor Cyan

# 1. 基础检查
foreach ($cmd in @("git", "node", "python")) {
  $ok = Get-Command $cmd -ErrorAction SilentlyContinue
  if ($ok) { Write-Host "[OK] $cmd $($ok.Version)" } else { Write-Host "[缺失] $cmd —— 请先安装" -ForegroundColor Red }
}

# 2. git 全局身份（与历史提交一致，可按需修改）
$gitName = git config --global user.name
$gitEmail = git config --global user.email
if (-not $gitName)  { git config --global user.name  "咕咕涛";            Write-Host "已设 user.name" }
if (-not $gitEmail) { git config --global user.email "1973226988@qq.com"; Write-Host "已设 user.email" }

# 3. SSH 公钥指纹核对（公钥需已录入 GitHub）
$pub = "$HOME\.ssh\id_ed25519.pub"
if (Test-Path $pub) {
  Write-Host "本机公钥指纹:"
  ssh-keygen -lf $pub
} else {
  Write-Host "未发现 SSH 密钥，请运行: ssh-keygen -t ed25519" -ForegroundColor Yellow
}

# 4. 拉取项目仓库（按需取消注释）
# git clone git@github.com:guguktao-byte/hub.git D:\pythonProject\hub
# git clone https://gitee.com/KTtao/camelot-service.git D:\pythonProject\卡密服务

Write-Host "== bootstrap 完成 ==" -ForegroundColor Cyan
