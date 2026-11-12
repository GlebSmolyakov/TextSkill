#!/usr/bin/env python3
"""Check Russian text against a stoplist, ignoring quoted text and code."""

import argparse
from bisect import bisect_right
import json
from pathlib import Path
import re
import sys


FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
INLINE = re.compile(
    r"https?://\S+"
    r"|(?<!`)(`{1,2})(?!`)[^\r\n]*?(?<!`)\1(?!`)"
    r"|«[^»\r\n]*»",
    re.IGNORECASE,
)
DASH = re.compile(r"—|(?<=\s)–(?=\s)")


def load_stoplist(path):
    rules = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        if "\t" not in line:
            raise ValueError(f"{path}:{number}: expected rule<TAB>pattern")
        rule, pattern = line.split("\t", 1)
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except (re.error, OverflowError) as error:
            raise ValueError(f"{path}:{number}: {rule}: {error}") from error
        rules.append((rule, compiled))
    return rules


def mask_text(text):
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line.rstrip("\r\n"))
        if fence is not None:
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                fence = None
            lines.append(re.sub(r"[^\r\n]", " ", line))
        elif re.match(r"\s*>", line):
            lines.append(re.sub(r"[^\r\n]", " ", line))
        elif marker:
            fence = marker[1]
            lines.append(re.sub(r"[^\r\n]", " ", line))
        else:
            lines.append(INLINE.sub(lambda match: " " * len(match[0]), line))
    return "".join(lines)


def lint_text(text, path, rules):
    masked = mask_text(text)
    line_starts = [0] + [match.end() for match in re.finditer("\n", text)]

    def finding(rule, match):
        line = bisect_right(line_starts, match.start())
        return {
            "path": path,
            "line": line,
            "col": match.start() - line_starts[line - 1] + 1,
            "rule": rule,
            "match": text[match.start():match.end()],
        }

    findings = []
    for rule, pattern in rules:
        findings.extend(finding(rule, match) for match in pattern.finditer(masked))
    # Test dash neighbours in the source: masking must not create whitespace.
    for match in DASH.finditer(text):
        if masked[match.start()] == match[0]:
            findings.append(finding("dash", match))
    return findings


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="strict")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--stoplist", type=Path, default=Path(__file__).with_name("stoplist.txt")
    )
    parser.add_argument("files", nargs="*", metavar="FILE")
    args = parser.parse_args()

    try:
        rules = load_stoplist(args.stoplist)
        findings = []
        for path in args.files or ["-"]:
            text = (
                sys.stdin.read()
                if path == "-"
                else Path(path).read_text(encoding="utf-8")
            )
            file_findings = lint_text(text, path, rules)
            file_findings.sort(key=lambda item: (item["line"], item["col"]))
            findings.extend(file_findings)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"{parser.prog}: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(findings, ensure_ascii=False))
    else:
        for item in findings:
            print(
                f"{item['path']}:{item['line']}:{item['col']}: "
                f"{item['rule']}: {item['match']}"
            )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
