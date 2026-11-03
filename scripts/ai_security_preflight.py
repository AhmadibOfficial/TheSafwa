#!/usr/bin/env python3
"""Pre-commit / CI confidentiality gate. Never prints matching credential values.

Use --staged in a hook and --tracked in CI. No third-party dependencies.
This is defense in depth; GitHub also runs Gitleaks and CodeQL.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
MAX_TEXT_SIZE = 3_000_000
TEXT_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".jsonc", ".yaml",
    ".yml", ".md", ".html", ".css", ".txt", ".xml", ".toml", ".sh",
    ".ini", ".cfg", ".sql", ".properties", ".gitignore",
}
SIGNATURES = (
    ("private-key-header", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")),
    ("github-access-token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("github-fine-grained-token", re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{35,}\b")),
    ("aws-access-key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("openai-style-token", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b")),
    ("gitlab-access-token", re.compile(rb"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("slack-access-token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
)
ASSIGNMENT = re.compile(
    rb"(?i)\b(?:api[_-]?key|client[_-]?secret|auth[_-]?token|access[_-]?token|password)\b\s*[:=]\s*[\"']([^\"'\r\n]{12,})[\"']"
)
PLACEHOLDERS = (
    b"example", b"placeholder", b"dummy", b"redacted", b"not-a-real",
    b"replace-me", b"changeme", b"test-only", b"your-", b"<", b"${",
    b"process.env", b"os.environ",
)

def blocked_path(path: str) -> bool:
    parts = Path(path).parts
    if not parts:
        return False
    parts_lower = tuple(p.lower() for p in parts)
    name = parts_lower[-1]
    if any(p in {"secrets", "private", "private-data", "client-data", "credentials"}
           for p in parts_lower[:-1]):
        return True
    if name == ".env" or (name.startswith(".env.") and name not in {".env.example", ".env.sample"}):
        return True
    if name in {".netrc", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"}:
        return True
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")):
        return True
    if "service-account" in name and name.endswith(".json"):
        return True
    return False

def inspect_content(path: str, content: bytes) -> list[str]:
    if len(content) > MAX_TEXT_SIZE or b"\x00" in content:
        return []
    if Path(path).suffix.lower() not in TEXT_EXTS and Path(path).name not in {".gitignore", "AGENTS.md", "CLAUDE.md"}:
        return []
    results = [label for label, matcher in SIGNATURES if matcher.search(content)]
    for match in ASSIGNMENT.finditer(content):
        value = match.group(1).strip().lower()
        if not any(placeholder in value for placeholder in PLACEHOLDERS):
            results.append("hardcoded-credential")
            break
    return results

def git(*args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"Git query failed ({args[0]}). Run inside a Git repository.")
    return proc.stdout

def selected_files(staged: bool) -> list[str]:
    raw = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z") if staged else git("ls-files", "-z")
    return [p.decode("utf-8", errors="surrogateescape") for p in raw.split(b"\0") if p]

def read_file(path: str, staged: bool) -> bytes:
    if staged:
        return git("show", f":{path}")
    file_path = ROOT / path
    if not file_path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("file resolves outside repository")
    if file_path.is_symlink():
        raise ValueError("symlink file requires separate review")
    return file_path.read_bytes()

def main() -> int:
    parser = argparse.ArgumentParser(description="Safwa confidentiality gate")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--tracked", action="store_true")
    args = parser.parse_args()
    findings: list[tuple[str, str]] = []
    try:
        files = selected_files(args.staged)
        for path in files:
            if blocked_path(path):
                findings.append((path, "forbidden-sensitive-file"))
                continue
            try:
                content = read_file(path, args.staged)
            except (OSError, ValueError, RuntimeError):
                findings.append((path, "unreadable-file"))
                continue
            findings.extend((path, rule) for rule in inspect_content(path, content))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for path, rule in findings:
        print(f"BLOCKED {path}: {rule}", file=sys.stderr)
    if findings:
        print(f"SECURITY FAIL: {len(findings)} finding(s). No secret values were printed.", file=sys.stderr)
        return 1
    print(f"SECURITY PASS: checked {len(files)} {'staged' if args.staged else 'tracked'} files.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
