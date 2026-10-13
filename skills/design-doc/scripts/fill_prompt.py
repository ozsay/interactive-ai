#!/usr/bin/env python3
"""Fill a prompt template's {{KEYS}}.

Usage: fill_prompt.py <template.md> <out.md> KEY=value [KEY=@file ...]

`@file` inserts that file's contents. Unfilled keys are an error, so a prompt never goes out with a
literal {{KEY}} in it.
"""
import re
import sys


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    vals = {}
    for kv in a[2:]:
        k, _, v = kv.partition("=")
        vals[k] = open(v[1:], encoding="utf-8").read().strip() if v.startswith("@") else v
    text = open(a[0], encoding="utf-8").read()
    missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", text)) - set(vals))
    if missing:
        sys.exit("missing values for: " + ", ".join(missing))
    open(a[1], "w", encoding="utf-8").write(re.sub(r"\{\{(\w+)\}\}", lambda m: vals[m.group(1)], text))
    print(a[1])


if __name__ == "__main__":
    main()
