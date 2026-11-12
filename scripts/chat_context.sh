#!/usr/bin/env bash
# SessionStart-хук: кладёт в контекст сессии карточки ответов в чате и личные образцы автора.
# Один раз на старт, resume и compact, а не на каждый запрос: карточки весят около 2 тыс. токенов.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVENT="${1:-SessionStart}"

{
  sed -n '/^## Как строить ответ в чате/,$p' "$ROOT/chat-style.md"
  if [[ -f "$ROOT/style-profile.local.md" ]]; then
    echo
    sed -n '/^## Образцы: ответы агента в чате/,$p' "$ROOT/style-profile.local.md"
  fi
} | jq -Rs --arg ev "$EVENT" '{hookSpecificOutput: {hookEventName: $ev, additionalContext: .}}'
