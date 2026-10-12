#!/usr/bin/env bash
# Design-system guardrails for frontend/src (CLAUDE.md › Non-negotiable rules, PLAN §7.4).
set -euo pipefail
cd "$(dirname "$0")/../frontend/src"
fail=0

check() { # $1 = message, rest = grep args
  local msg=$1; shift
  if out=$(grep -rnE "$@" . 2>/dev/null); then
    echo "✗ $msg"; echo "$out"; fail=1
  fi
}

# Colors only via tokens (CSS variables / Tailwind token utilities).
check "hard-coded hex/rgb color (use a token)" --include='*.vue' --include='*.css' --include='*.ts' \
  -e '#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?([0-9a-fA-F]{2})?\b[^-]' -e '\brgba?\(' --exclude='*.spec.ts'
# Never white text on the lavender fill; Tailwind's palette colors are off-limits.
check "white / non-token text color" --include='*.vue' -e '\btext-(white|black)\b' -e '\bbg-(white|black)\b'
check "default Tailwind palette color (use a token)" --include='*.vue' \
  -e '\b(bg|text|border|ring|fill|stroke)-(red|green|blue|gray|slate|zinc|neutral|stone|amber|yellow|emerald|rose|pink|purple|indigo|sky)-[0-9]{2,3}\b'
# Icons: Hugeicons only, through the concept map.
check "icon import outside lib/icons.ts (use <AppIcon name>)" --include='*.vue' --include='*.ts' \
  -e "from '@hugeicons/core-free-icons'" --exclude='icons.ts'
check "ASCII hyphen used as a minus sign in a P/L literal" --include='*.vue' -e "['\"]-\\\$[0-9]"

if [ $fail -eq 0 ]; then echo "✓ design rules OK"; fi
exit $fail
