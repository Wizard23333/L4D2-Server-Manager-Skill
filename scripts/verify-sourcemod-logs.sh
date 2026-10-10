#!/bin/bash
# 只读检查 SourceMod 错误日志与当前启用插件。
# 用法：本地执行 ssh myubuntu2 'bash -s' < scripts/verify-sourcemod-logs.sh
#      或先 scp 到服务器再执行。本脚本不修改任何服务器状态。
# 注意：从 Windows PowerShell 管道执行时中文输出可能因控制台代码页显示为乱码，
#       插件名/文件名等 ASCII 内容不受影响；需正常中文请用 Git Bash 或 SSH 终端。
SM=/opt/l4d2/left4dead2/addons/sourcemod
today=$(date +%Y%m%d)
LOG="$SM/logs/errors_$today.log"

if [ ! -f "$LOG" ]; then
  echo "今天没有错误日志文件：$LOG"
  echo "（服务器当天未产生 SM 错误，或日志已被轮转；可用 ls $SM/logs/ 查看历史）"
else
  echo "=== $LOG 中最后一个 error session 之后的内容 ==="
  # 显示最后一次 session 开始之后的行，用于判断最近一次启动是否仍在报错
  awk '/error session started/{buf=""} {buf=buf $0 "\n"} END{print buf}' "$LOG" | tail -n 20
  echo
  echo "=== 完整末尾 12 行 ==="
  tail -n 12 "$LOG"
fi

echo
echo "=== 当前启用的插件 ==="
ls "$SM/plugins/"*.smx 2>/dev/null | xargs -n1 basename | tr '\n' ' '; echo

echo
echo "=== 当前禁用的插件（禁用态也是状态，备份/迁移需一并带走） ==="
ls "$SM/plugins/disabled/"*.smx 2>/dev/null | xargs -n1 basename | tr '\n' ' '; echo