#!/usr/bin/env python3
"""Fill a prompt template's {{KEYS}}.

Usage: fill_prompt.py <template.md> <out.md> KEY=value [KEY=@file ...]

`@file` inserts that file's contents. A value that is a path (an existing file, or a
new file in an existing folder) is made absolute. Unfilled keys are an error, so a prompt never
goes out with a literal {{KEY}} in it.
"""
import os
import re
import sys


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    vals = {}
    for kv in a[2:]:
        k, _, v = kv.partition("=")
        if v.startswith("@"):
            vals[k] = open(v[1:], encoding="utf-8").read().strip()
        else:
            # The prompt is read by an agent in another cwd, so a path must be absolute.
            is_path = os.path.exists(v) or ("/" in v and " " not in v and os.path.isdir(os.path.dirname(v) or "."))
            vals[k] = os.path.abspath(v) if is_path else v
    text = open(a[0], encoding="utf-8").read()
    missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", text)) - set(vals))
    if missing:
        sys.exit("missing values for: " + ", ".join(missing))
    open(a[1], "w", encoding="utf-8").write(re.sub(r"\{\{(\w+)\}\}", lambda m: vals[m.group(1)], text))
    print(a[1])


if __name__ == "__main__":
    main()
