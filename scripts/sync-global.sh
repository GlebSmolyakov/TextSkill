#!/usr/bin/env bash
# Публикует ядро и скиллы TextSkill в ~/.claude, чтобы они работали в любом проекте,
# не только в этом репозитории. Перезапускай после любых правок writing-rules.md,
# mosty.md, audit.md, voices/ или .claude/skills/*/SKILL.md, иначе глобальная копия устареет.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DST="$HOME/.claude/textskill"
SKILLS_DST="$HOME/.claude/skills"

SKILLS=(
  audit-docs audit-text rewrite-text style-profile
  write-article write-docs write-email write-kp write-landing
  write-post write-press-release write-readme write-resume write-vacancy
)

echo "Синхронизирую ядро в $CORE_DST"
mkdir -p "$CORE_DST/voices"
cp "$SRC/writing-rules.md" "$CORE_DST/writing-rules.md"
cp "$SRC/mosty.md" "$CORE_DST/mosty.md"
cp "$SRC/audit.md" "$CORE_DST/audit.md"
cp "$SRC"/voices/*.md "$CORE_DST/voices/"

# В глобальном writing-rules.md нет "корня проекта" — self-хук на профиль голоса
# должен указывать на фиксированный путь, иначе скиллы вне репозитория его не найдут.
tmp="$(mktemp)"
sed \
  -e "s|в корне проекта есть файл \`style-profile.local.md\`|есть файл \`$CORE_DST/style-profile.local.md\`|g" \
  "$CORE_DST/writing-rules.md" > "$tmp"
mv "$tmp" "$CORE_DST/writing-rules.md"

echo "Синхронизирую ${#SKILLS[@]} скиллов в $SKILLS_DST"
for name in "${SKILLS[@]}"; do
  mkdir -p "$SKILLS_DST/$name"
  tmp="$(mktemp)"
  sed \
    -e "s|\`writing-rules.md\` и \`mosty.md\` из корня проекта|\`$CORE_DST/writing-rules.md\` и \`$CORE_DST/mosty.md\`|g" \
    -e "s|\`writing-rules.md\` и \`mosty.md\` из корня,|\`$CORE_DST/writing-rules.md\` и \`$CORE_DST/mosty.md\`,|g" \
    -e "s|\`writing-rules.md\` и \`mosty.md\`, чтобы|\`$CORE_DST/writing-rules.md\` и \`$CORE_DST/mosty.md\`, чтобы|g" \
    -e "s|Прочитай также \`mosty.md\` из корня,|Прочитай также \`$CORE_DST/mosty.md\`,|g" \
    -e "s|\`writing-rules.md\` (база паттернов), \`mosty.md\` (|\`$CORE_DST/writing-rules.md\` (база паттернов), \`$CORE_DST/mosty.md\` (|g" \
    -e "s|\`writing-rules.md\` из корня проекта|\`$CORE_DST/writing-rules.md\`|g" \
    -e "s|\`writing-rules.md\` из корня|\`$CORE_DST/writing-rules.md\`|g" \
    -e "s|Если в корне есть \`style-profile.local.md\`|Если есть \`$CORE_DST/style-profile.local.md\`|g" \
    -e "s|Если есть \`style-profile.local.md\`|Если есть \`$CORE_DST/style-profile.local.md\`|g" \
    -e "s|в корне есть \`style-profile.local.md\`|есть \`$CORE_DST/style-profile.local.md\`|g" \
    -e "s|Если \`style-profile.local.md\` уже есть|Если файл \`$CORE_DST/style-profile.local.md\` уже есть|g" \
    -e "s|\`style-profile.local.md\` в корне проекта|\`$CORE_DST/style-profile.local.md\`|g" \
    -e "s|из \`voices/\`|из \`$CORE_DST/voices/\`|g" \
    -e "s|в \`voices/habr.md\`|в \`$CORE_DST/voices/habr.md\`|g" \
    -e "s|\`.claude/skills/write-docs/SKILL.md\`|\`$SKILLS_DST/write-docs/SKILL.md\`|g" \
    -e "s| (жанровые правила доков плюс override регистра) из корня проекта\.| (жанровые правила доков плюс override регистра).|g" \
    -e "s|Файл локальный, в гит не попадает (\`\*.local.md\` в \`.gitignore\`), не предлагай его коммитить.|Файл живёт в \`~/.claude/textskill/\`, вне какого-либо репозитория и общий для всех проектов, коммитить его никуда не нужно.|g" \
    -e "s|Напомни, что файл локальный и в гит не идёт.|Напомни, что файл общий на все проекты (лежит в \`~/.claude/textskill/\`, а не в текущем репозитории).|g" \
    "$SRC/.claude/skills/$name/SKILL.md" > "$tmp"
  mv "$tmp" "$SKILLS_DST/$name/SKILL.md"
done

echo "Готово. Ядро: $CORE_DST, скиллы: $SKILLS_DST/{${SKILLS[*]}}"
