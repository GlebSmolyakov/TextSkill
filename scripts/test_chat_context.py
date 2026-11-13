import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("chat_context.sh")


def run_hook(chat_style, profile=None, args=(), env=None):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "scripts").mkdir()
        shutil.copy(SCRIPT, root / "scripts" / "chat_context.sh")
        (root / "chat-style.md").write_text(chat_style, encoding="utf-8")
        if profile is not None:
            (root / "style-profile.local.md").write_text(profile, encoding="utf-8")
        result = subprocess.run(
            ["bash", str(root / "scripts" / "chat_context.sh"), *args],
            capture_output=True, text=True, env=env, check=True,
        )
        return json.loads(result.stdout), result.stderr


CARDS = "Шапка файла\n\n## Как строить ответ в чате\n\nКарточки.\n"
PROFILE = "Голос\n\n## Образцы: ответы агента в чате\n\nОбразец ответа.\n"


class ChatContextTest(unittest.TestCase):
    def test_cards_and_samples_without_header(self):
        out, _ = run_hook(CARDS, PROFILE)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(ctx.startswith("## Как строить ответ в чате"))
        self.assertIn("Образец ответа.", ctx)
        self.assertNotIn("Шапка файла", ctx)
        self.assertNotIn("Голос", ctx.split("## Образцы")[0])

    def test_heading_mentioned_mid_line_is_not_a_start(self):
        cards = "Подключается через «## Как строить ответ в чате» хуком.\n\n" + CARDS
        out, _ = run_hook(cards)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(ctx.startswith("## Как строить ответ в чате\n"))
        self.assertNotIn("Подключается", ctx)

    def test_event_name_from_argument(self):
        out, _ = run_hook(CARDS, PROFILE, args=["SubagentStart"])
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SubagentStart")

    def test_default_event_is_session_start(self):
        out, _ = run_hook(CARDS)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_without_profile_only_cards(self):
        out, _ = run_hook(CARDS)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Карточки.", ctx)
        self.assertNotIn("Образцы", ctx)

    def test_over_limit_drops_samples_and_points_to_profile(self):
        big_profile = PROFILE + "x" * 500
        out, err = run_hook(CARDS, big_profile, env={"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "CHAT_CONTEXT_LIMIT": "200"})
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(ctx), 200)
        self.assertIn("Карточки.", ctx)
        self.assertNotIn("x" * 50, ctx)
        self.assertIn("style-profile.local.md", ctx)
        self.assertIn("лимит", err)

    def test_limit_counts_characters_not_bytes(self):
        profile = PROFILE + "я" * 60
        size = len(CARDS.split("## Как", 1)[1]) + len(profile) + 40
        out, err = run_hook(CARDS, profile, env={"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "CHAT_CONTEXT_LIMIT": str(size)})
        self.assertIn("я" * 60, out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
