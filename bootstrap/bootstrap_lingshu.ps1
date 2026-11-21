param([Parameter(ValueFromRemainingArguments = $true)]$Rest)
$ErrorActionPreference = "Stop"
python (Join-Path $PSScriptRoot "bootstrap_lingshu.py") @Rest
