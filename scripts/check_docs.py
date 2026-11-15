"""Validate local documentation without network access or printing document text."""
from pathlib import Path
import html
import json
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

CANONICAL = {"README.md", "CONTRIBUTING.md", "SECURITY.md", "docs/architecture.md", "docs/operations.md",
             "docs/verification-lab.md", "docs/compatibility.md", "docs/security.md", "docs/evaluation.md"}
PRIVATE = re.compile(r"(?:C:[\\/]Users[\\/]|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|tvly-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,})")


def prose(text):
    output, fence = [], None
    for line in text.splitlines():
        mark = re.match(r"^\s*(`{3,}|~{3,})", line)
        if mark:
            value = mark.group(1)
            if fence is None:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = None
            output.append("")
        else:
            output.append("" if fence else line)
    return "\n".join(output), fence is not None


def anchors(text):
    used = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", text, re.M):
        heading = re.sub(r"!?\[([^]]+)\]\([^)]*\)", r"\1", heading)
        heading = re.sub(r"<[^>]*>", "", html.unescape(heading)).replace("`", "").lower()
        base = "".join(c for c in heading if c in "-_ " or unicodedata.category(c)[0] in "LN").replace(" ", "-")
        slug, index = base, 0
        while slug in used:
            index += 1
            slug = f"{base}-{index}"
        used.add(slug)
    used.update(re.findall(r'''<[^>]+(?:id|name)=["']([^"']+)["']''', text))
    return used


def check(root, names):
    root = root.resolve()
    failures, texts, headings = [], {}, {}
    links = anchor_links = paths = 0
    for name in names:
        try:
            raw = (root / name).read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError):
            failures.append((name, "invalid UTF-8 or unreadable file"))
            continue
        text, unclosed = prose(raw)
        texts[name], headings[name] = text, anchors(text)
        if unclosed:
            failures.append((name, "unclosed code fence"))
        if PRIVATE.search(raw):
            failures.append((name, "forbidden credential or private workstation path pattern"))
        if not raw.endswith("\n") or "\x00" in raw:
            failures.append((name, "missing final newline or NUL"))
        if name in CANONICAL:
            references = re.findall(r"`((?:dev|scripts|tests|services|plugins|internal|cmd|web|\.github)/[\w./-]+)`", raw)
            references += re.findall(r"(?:python3?\s+|py -3\.12\s+)([\w./-]+\.py)\b", raw)
            for reference in references:
                paths += 1
                if not (root / reference).exists():
                    failures.append((name, "missing repository path: " + reference))
    for name, text in texts.items():
        definitions = dict(re.findall(r"^\[([^]]+)\]:\s*(\S+)", text, re.M))
        targets = re.findall(r"!?\[[^]\n]*\]\(([^)\n]+)\)", text) + list(definitions.values())
        for target in targets:
            target = target.strip("<>").split()[0]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            dest = ((root / name).parent / unquote(parsed.path)).resolve() if parsed.path else root / name
            if not dest.is_relative_to(root) or not dest.exists():
                failures.append((name, "missing or external local link"))
                continue
            links += 1
            if parsed.fragment:
                anchor_links += 1
                if unquote(parsed.fragment) not in headings.get(dest.relative_to(root).as_posix(), set()):
                    failures.append((name, "missing local anchor"))
        for reference in re.findall(r"\[[^]\n]+\]\[([^]\n]+)\]", text):
            if reference not in definitions:
                failures.append((name, "undefined link reference"))
    return failures, {"markdown_files": len(texts), "local_links": links, "anchor_links": anchor_links, "repository_paths": paths}


def main():
    root = Path(__file__).resolve().parents[1]
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.md"], cwd=root, text=True).splitlines()
    failures, counts = check(root, names)
    for name, reason in failures:
        print(f"{name}: {reason}", file=sys.stderr)
    print(json.dumps(counts, sort_keys=True))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
