#!/bin/bash
# ワークスペース（推し活アプリ/tools/security_check.sh）の検査を、このリポジトリに絞って呼ぶラッパー。
# 契約: --quick / --gate / --full。CRITICAL があれば exit 1。
# 方針: ../../../07_セキュリティAI/CLAUDE.md
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_CHECK="$REPO_ROOT/../../../tools/security_check.sh"
if [ ! -x "$WS_CHECK" ]; then
  echo "🔴 CRITICAL: ワークスペースの検査スクリプト $WS_CHECK が見つからない" >&2
  exit 1
fi
exec "$WS_CHECK" "${1:---quick}" "$REPO_ROOT"
