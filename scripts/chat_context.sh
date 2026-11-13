#!/usr/bin/env bash
# SessionStart-хук для Claude Code и Codex: кладёт в контекст сессии карточки ответов в чате и личные образцы автора.
# Один раз на старт, resume и compact, а не на каждый запрос: карточки весят около 2 тыс. токенов.
# Claude Code принимает от одного хука до 10 000 символов additionalContext, больше молча обрезает.
# Поэтому образцы профиля отпадают с конца, пока текст не влезет в CHAT_CONTEXT_LIMIT (по умолчанию 9500).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVENT="${1:-SessionStart}"
LIMIT="${CHAT_CONTEXT_LIMIT:-9500}"

python3 - "$ROOT" "$EVENT" "$LIMIT" <<'PY'
import json
import re
import sys
from pathlib import Path

root, event, limit = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
cards = (root / "chat-style.md").read_text(encoding="utf-8")
cards = cards[re.search(r"(?m)^## Как строить ответ в чате", cards).start():]

profile = root / "style-profile.local.md"
sections = []
if profile.exists():
    text = profile.read_text(encoding="utf-8")
    found = re.search(r"(?m)^## Образцы: ответы агента в чате", text)
    if found:
        sections = [s for s in re.split(r"(?m)^(?=## )", text[found.start():]) if s]


def build(parts, note=""):
    return cards + ("\n" + "".join(parts) if parts else "") + note


note = f"\n\nОстальные образцы голоса автора в {profile}, прочитай их, когда пишешь текст в его голосе.\n"
context = build(sections)
while len(context) > limit and sections:
    sections.pop()
    context = build(sections, note)
if len(context) > limit:
    context = context[:limit]
if context != build(sections) or len(build(sections)) > limit:
    print(f"chat_context: лимит {limit} символов, часть образцов не вошла", file=sys.stderr)

print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}, ensure_ascii=False))
PY
