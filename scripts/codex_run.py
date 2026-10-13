#!/usr/bin/env python3
"""Run one read-only Codex pass and save its JSON answer.

Usage: codex_run.py check
       codex_run.py <prompt.md> <schema.json> <out.json> <cwd> --role reviewer|verifier [--timeout 1200]

`check` exits 0 when the codex CLI is installed and logged in, else prints why and exits 69.
A run feeds the prompt on stdin to `codex exec` in a read-only sandbox, with no approvals and no
MCP servers, constrained to the schema. Events go to <out.json>.events.jsonl, stderr to
<out.json>.err. Exits non-zero, writing nothing to <out.json>, when the answer is missing or not JSON.
The role picks the model and reasoning effort from models.json. Writes <out.json>.meta.json with
the model and effort the session actually ran with, read from Codex's session log.
"""
import json
import os
import shutil
import signal
import subprocess
import sys


def find_codex():
    """PR_TOUR_CODEX, then PATH, then the user's login shell (agent shells often lack its PATH)."""
    if os.environ.get("PR_TOUR_CODEX"):
        return os.environ["PR_TOUR_CODEX"]
    if shutil.which("codex"):
        return shutil.which("codex")
    import pwd
    for shell in dict.fromkeys([pwd.getpwuid(os.getuid()).pw_shell, os.environ.get("SHELL", "")]):
        if not shell:
            continue
        res = subprocess.run([shell, "-lc", "command -v codex"], capture_output=True, text=True)
        path = (res.stdout.strip().splitlines() or [""])[-1]
        if path and os.access(path, os.X_OK):
            return path
    return None


CODEX = find_codex()


def check():
    if not CODEX:
        print("codex CLI not found. Install it (https://github.com/openai/codex), run `codex login`, or set PR_TOUR_CODEX to its path.")
        return 69
    if subprocess.run([CODEX, "login", "status"], capture_output=True).returncode:
        print("codex is not logged in. Run `codex login`.")
        return 69
    return 0


def main():
    args = sys.argv[1:]
    if args[:1] == ["check"]:
        sys.exit(check())
    if len(args) < 4:
        sys.exit(__doc__)
    prompt, schema, out, cwd = (os.path.abspath(a) for a in args[:4])  # codex runs in cwd
    timeout = int(args[args.index("--timeout") + 1]) if "--timeout" in args else 1200
    role = args[args.index("--role") + 1] if "--role" in args else sys.exit("--role reviewer|verifier is required")
    pick = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models.json")))[role]["codex"]
    if check():
        sys.exit(69)
    text = out + ".txt"
    cmd = [CODEX, "exec", "--skip-git-repo-check", "--json",
           "--config", 'sandbox_mode="read-only"', "--config", 'approval_policy="never"',
           "--config", f'model_reasoning_effort="{pick["effort"]}"', "--config", "mcp_servers={}",
           "-m", pick["model"], "--output-schema", schema, "-o", text, "-"]
    with open(prompt) as stdin, open(out + ".events.jsonl", "w") as stdout, open(out + ".err", "w") as stderr:
        proc = subprocess.Popen(cmd, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            sys.exit(f"codex timed out after {timeout}s")
    if code:
        sys.exit(f"codex exited {code}; see {out}.err")
    try:
        answer = json.load(open(text))
    except (OSError, ValueError) as e:
        sys.exit(f"codex gave no JSON answer ({e}); see {out}.events.jsonl")
    json.dump(answer, open(out, "w"), indent=1)
    json.dump(session_meta(out + ".events.jsonl", pick), open(out + ".meta.json", "w"))
    print(out)


def session_meta(events, pick):
    """What the session really ran with, from ~/.codex/sessions; falls back to what was asked for."""
    meta = {"model": pick["model"], "effort": pick["effort"], "label": pick["label"], "confirmed": False}
    try:
        thread = next(json.loads(l)["thread_id"] for l in open(events) if '"thread.started"' in l)
        import glob
        log = next(iter(glob.glob(os.path.expanduser(f"~/.codex/sessions/**/*{thread}.jsonl"), recursive=True)), None)
        text = open(log).read() if log else ""
        import re
        models = set(re.findall(r'"model":"([^"]+)"', text))
        efforts = set(re.findall(r'"(?:reasoning_)?effort":"([^"]+)"', text))
        if models:
            meta.update(model=", ".join(sorted(models)), confirmed=True)
        if efforts:
            meta["effort"] = ", ".join(sorted(efforts))
        meta["thread"] = thread
    except (OSError, StopIteration, ValueError, KeyError):
        pass
    return meta


if __name__ == "__main__":
    main()
