import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("lint_text.py")


def run(text=None, *args, stoplist=None):
    cmd = [sys.executable, str(SCRIPT)]
    if stoplist is not None:
        cmd += ["--stoplist", str(stoplist)]
    cmd += list(args)
    return subprocess.run(cmd, input=text, capture_output=True, text=True, encoding="utf-8")


def findings(text, stoplist=None):
    res = run(text, "--format", "json", stoplist=stoplist)
    return res.returncode, json.loads(res.stdout or "[]")


class TmpStoplist:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        path = Path(self.dir.name) / "stop.txt"
        path.write_text(self.body, encoding="utf-8")
        return path

    def __exit__(self, *exc):
        self.dir.cleanup()


EMPTY = "# пусто\n"


class DashTest(unittest.TestCase):
    def test_em_dash_with_position(self):
        with TmpStoplist(EMPTY) as sl:
            code, f = findings("Первая строка\nТекст — пояснение\n", sl)
        self.assertEqual(code, 1)
        self.assertEqual([(x["rule"], x["line"], x["col"], x["match"]) for x in f], [("dash", 2, 7, "—")])

    def test_spaced_en_dash_is_dash(self):
        with TmpStoplist(EMPTY) as sl:
            code, f = findings("Текст – пояснение\n", sl)
        self.assertEqual([x["rule"] for x in f], ["dash"])

    def test_en_dash_in_range_is_fine(self):
        with TmpStoplist(EMPTY) as sl:
            code, f = findings("Займёт 3–5 минут, строки 40–90.\n", sl)
        self.assertEqual((code, f), (0, []))

    def test_hyphen_is_fine(self):
        with TmpStoplist(EMPTY) as sl:
            code, f = findings("Что-то вроде пул-реквеста, ок - иду дальше.\n", sl)
        self.assertEqual((code, f), (0, []))


class MaskingTest(unittest.TestCase):
    def test_fenced_code_ignored(self):
        text = "До\n```\nx = a — b\n```\n~~~\nважно отметить\n~~~\nПосле\n"
        with TmpStoplist("связка\t\\bважно отметить\\b\n") as sl:
            self.assertEqual(findings(text, sl), (0, []))

    def test_inline_code_ignored_and_columns_kept(self):
        text = "Флаг `--a — b` и тут — тире\n"
        with TmpStoplist(EMPTY) as sl:
            code, f = findings(text, sl)
        self.assertEqual([(x["line"], x["col"]) for x in f], [(1, 22)])

    def test_double_backtick_inline_code_ignored(self):
        with TmpStoplist(EMPTY) as sl:
            self.assertEqual(findings("Код ``a ` — b`` тут\n", sl), (0, []))

    def test_guillemet_quote_ignored(self):
        text = "Ты написал «важно отметить — это главное», я поправил.\n"
        with TmpStoplist("связка\t\\bважно отметить\\b\n") as sl:
            self.assertEqual(findings(text, sl), (0, []))

    def test_blockquote_ignored(self):
        text = "> Безусловно — это цитата\n  > и это тоже — цитата\nА это — нет\n"
        with TmpStoplist("связка\t\\bбезусловно\\b\n") as sl:
            code, f = findings(text, sl)
        self.assertEqual([(x["rule"], x["line"]) for x in f], [("dash", 3)])

    def test_url_ignored(self):
        with TmpStoplist("паразит\t\\bданный\\b\n") as sl:
            self.assertEqual(findings("См. https://x.ru/данный—путь тут\n", sl), (0, []))


class StoplistEngineTest(unittest.TestCase):
    def test_case_insensitive_and_rule_name(self):
        with TmpStoplist("связка\t\\bважно отметить\\b\n") as sl:
            code, f = findings("Важно отметить, что тест упал.\n", sl)
        self.assertEqual(code, 1)
        self.assertEqual([(x["rule"], x["col"], x["match"]) for x in f], [("связка", 1, "Важно отметить")])

    def test_comments_and_blank_lines_skipped(self):
        with TmpStoplist("# комментарий\n\nпаразит\t\\bданный\\b\n") as sl:
            code, f = findings("данный метод\n", sl)
        self.assertEqual([x["rule"] for x in f], ["паразит"])

    def test_findings_sorted_by_position(self):
        body = "a\t\\bвторое\\b\nb\t\\bпервое\\b\n"
        with TmpStoplist(body) as sl:
            code, f = findings("первое и второе\nпервое\n", sl)
        self.assertEqual([(x["line"], x["col"]) for x in f], [(1, 1), (1, 10), (2, 1)])

    def test_text_format(self):
        with TmpStoplist("паразит\t\\bданный\\b\n") as sl:
            res = run("Это данный метод\n", stoplist=sl)
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stdout.strip(), "-:1:5: паразит: данный")

    def test_file_argument_path_in_output(self):
        with TmpStoplist("паразит\t\\bданный\\b\n") as sl, tempfile.TemporaryDirectory() as d:
            p = Path(d) / "msg.md"
            p.write_text("ок\nданный\n", encoding="utf-8")
            res = run(None, str(p), stoplist=sl)
        self.assertEqual(res.stdout.strip(), f"{p}:2:1: паразит: данный")

    def test_clean_text_exit_zero_and_empty_output(self):
        with TmpStoplist("паразит\t\\bданный\\b\n") as sl:
            res = run("Всё чисто.\n", stoplist=sl)
        self.assertEqual((res.returncode, res.stdout), (0, ""))


class ErrorsTest(unittest.TestCase):
    def test_missing_file_exit_2(self):
        res = run(None, "/nonexistent/file.md")
        self.assertEqual(res.returncode, 2)
        self.assertTrue(res.stderr)

    def test_bad_regex_exit_2(self):
        with TmpStoplist("плохо\t(незакрытая\n") as sl:
            res = run("текст\n", stoplist=sl)
        self.assertEqual(res.returncode, 2)
        self.assertIn("плохо", res.stderr)

    def test_line_without_tab_exit_2(self):
        with TmpStoplist("без табуляции\n") as sl:
            res = run("текст\n", stoplist=sl)
        self.assertEqual(res.returncode, 2)


class RealStoplistTest(unittest.TestCase):
    """Проверяет сам словарь scripts/stoplist.txt, а не движок."""

    def rules(self, text):
        code, f = findings(text)
        return {x["match"].lower() for x in f}

    def test_machine_text_caught(self):
        text = (
            "В современном мире тайм-менеджмент играет ключевую роль. "
            "Существует множество подходов, и важно отметить, что каждый случай индивидуален. "
            "Безусловно, данный подход является эффективным решением.\n"
        )
        got = self.rules(text)
        for m in ["в современном мире", "играет ключевую роль", "важно отметить",
                  "каждый случай индивидуален", "безусловно", "данный", "является", "эффективным решением"]:
            self.assertIn(m, got)

    def test_word_forms(self):
        got = self.rules("Они являются частью. Данная функция. Осуществляет проверку.\n")
        self.assertTrue({"являются", "данная", "осуществляет"} <= got)

    def test_data_noun_not_flagged(self):
        self.assertEqual(findings("По данным за октябрь данные не сходятся.\n"), (0, []))

    def test_author_markers_not_flagged(self):
        text = (
            "Началось всё с раздражения, если честно. По сути, это пока теория, "
            "короче, ещё подумаю. В итоге прогоняем через OCR, вроде работает, "
            "но зацепка интересная. Поэтому стираем старый текст и пишем новый.\n"
        )
        self.assertEqual(findings(text), (0, []))

    def test_chat_report_clean(self):
        text = (
            "Импорт теперь пропускает строки без артикула и пишет их в `skipped.csv`. "
            "Прогнал на выгрузке за октябрь: из 4812 строк пропущено 37, остальные легли. "
            "Дубли по артикулу не трогал, это отдельная правка.\n"
        )
        self.assertEqual(findings(text), (0, []))


if __name__ == "__main__":
    unittest.main()
