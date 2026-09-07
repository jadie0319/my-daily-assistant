#!/usr/bin/env python3
"""Validate (and optionally fix) a freshly created Obsidian summary note against
obsidian-note-rules.md. Deterministic backstop for the summarize skills — the
LLM may ignore prose rules, this script does not.

Checks
  1. tags: every tag must exist in {OBSIDIAN_VAULT}/95.Vault/태그 어휘.md
     (source/* included). 3-5 topic tags + one source/* tag.
  2. origin: must be `library`.
  3. related: must be present (empty list is fine).
  4. filename: no leading/trailing space, none of | # ^ : * ? " < > \\ /.

--fix
  - unknown tag -> nearest existing ancestor (ai/rag/modular-rag -> ai/rag -> ai/llm? no:
    only real ancestors; if none exists the tag is dropped and listed in an
    HTML comment `<!-- 태그 제안: ... -->` at the end of the body so the user can
    extend the vocabulary)
  - originals preserved once in `tags_original:`
  - adds `origin: library`, `related: []` when missing
  - renames the file if the filename breaks the rules (links are not rewritten;
    run this before anything links to the note)
Exit code 0 = compliant (after fix if --fix), 1 = violations remain / not fixed.

Usage:
  python3 scripts/check_obsidian_note.py "<path to note>" [--fix] [--vault "<vault root>"]
If --vault is omitted, OBSIDIAN_VAULT is read from env.config next to this repo.
"""
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
BAD_CHARS = '|#^:*?"<>\\/'


def nfc(s):
    return unicodedata.normalize("NFC", s)


def vault_root(explicit):
    if explicit:
        return explicit
    env = os.path.join(REPO, "env.config")
    with open(env, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("OBSIDIAN_VAULT="):
                return line.split("=", 1)[1].strip()
    sys.exit("OBSIDIAN_VAULT not found in env.config")


def load_vocab(vault):
    path = os.path.join(vault, "95.Vault", "태그 어휘.md")
    text = open(path, encoding="utf-8").read()
    tags = re.findall(r"^\| `([a-z0-9/\-]+)` \|", text, re.M)
    return {t for t in tags if not t.endswith("/")}


def list_block(fm, key):
    m = re.search(r"^%s:\s*\n((?:[ \t]+-[ \t]+.*\n?)+)" % re.escape(key), fm, re.M)
    if m:
        return [x.strip().strip("\"'") for x in re.findall(r"-\s+(.*)", m.group(1))], m.span()
    m = re.search(r"^%s:\s*\[(.*?)\]\s*$" % re.escape(key), fm, re.M)
    if m:
        return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()], m.span()
    return None, None


def nearest_ancestor(tag, vocab):
    parts = tag.lower().split("/")
    while len(parts) > 1:
        parts = parts[:-1]
        cand = "/".join(parts)
        if cand in vocab:
            return cand
    return None


def clean_stem(stem):
    s = re.sub(r"\s*\|\s*", " - ", stem)
    s = re.sub(r"[#^:*?\"<>\\/]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -")
    return s[:120].rstrip(" -")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    fix = "--fix" in args
    no_rename = "--no-rename" in args   # hook mode: never move the file the model is still editing
    vault = None
    if "--vault" in args:
        vault = args[args.index("--vault") + 1]
    path = [a for a in args if not a.startswith("--") and a != vault][0]
    vault = vault_root(vault)
    vocab = load_vocab(vault)

    text = open(path, encoding="utf-8").read()
    m = FM_RE.match(text)
    if not m:
        print("FAIL: no frontmatter")
        sys.exit(1)
    fm, body = m.group(1), text[m.end():]
    problems, fixes = [], []

    # --- tags
    tags, span = list_block(fm, "tags")
    tags = tags or []
    topic = [t for t in tags if not t.startswith("source/")]
    source_tags = [t for t in tags if t.startswith("source/")]
    unknown = [t for t in tags if t not in vocab]
    if unknown:
        problems.append("tags not in vocabulary: " + ", ".join(unknown))
    if not (3 <= len(topic) <= 5):
        problems.append("topic tag count %d (want 3-5)" % len(topic))
    if len(source_tags) != 1:
        problems.append("source/* tag count %d (want exactly 1)" % len(source_tags))
    if fix and (unknown or span):
        new, dropped = [], []
        for t in tags:
            t2 = t if t in vocab else nearest_ancestor(t, vocab)
            if t2 is None:
                dropped.append(t)
            elif t2 not in new:
                new.append(t2)
        if new != tags:
            already_orig, _ = list_block(fm, "tags_original")
            block = "tags:\n" + "".join("  - %s\n" % t for t in new)
            if already_orig is None:
                block += "tags_original:\n" + "".join("  - %s\n" % t for t in tags)
            fm = fm[:span[0]] + block + fm[span[1]:].lstrip("\n")
            fixes.append("tags -> " + ", ".join(new))
            if dropped:
                body = body.rstrip("\n") + "\n\n<!-- 태그 제안: %s (어휘표에 없어 제거됨. 필요하면 95.Vault/태그 어휘.md 에 추가) -->\n" % ", ".join(dropped)
                fixes.append("dropped (no ancestor in vocabulary): " + ", ".join(dropped))

    # --- origin
    om = re.search(r"^origin:\s*(\S+)", fm, re.M)
    if not om or om.group(1) != "library":
        problems.append("origin missing or not 'library'")
        if fix:
            fm = re.sub(r"^origin:.*\n?", "", fm, flags=re.M).rstrip("\n") + "\norigin: library"
            fixes.append("origin: library")

    # --- related
    if not re.search(r"^related:", fm, re.M):
        problems.append("related missing")
        if fix:
            fm = fm.rstrip("\n") + "\nrelated: []"
            fixes.append("related: []")

    # --- filename
    stem = nfc(os.path.splitext(os.path.basename(path))[0])
    good = clean_stem(stem)
    if stem != good:
        problems.append("filename breaks rules: %r -> %r" % (stem, good))

    if fix and fixes:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\n" + fm.rstrip("\n") + "\n---\n" + body)
    if fix and stem != good and not no_rename:
        newp = os.path.join(os.path.dirname(path), good + ".md")
        if not os.path.exists(newp):
            os.rename(path, newp)
            fixes.append("renamed -> %s.md" % good)
            path = newp

    print("note:", os.path.basename(path))
    if problems:
        print("violations:")
        for p in problems:
            print("  -", p)
    if fixes:
        print("fixed:")
        for f in fixes:
            print("  -", f)
    remaining = [] if fix and fixes else problems
    if fix and fixes:
        # re-check quickly
        text = open(path, encoding="utf-8").read()
        fm2 = FM_RE.match(text).group(1)
        tags2, _ = list_block(fm2, "tags")
        remaining = [t for t in (tags2 or []) if t not in vocab]
        if remaining:
            print("still unknown tags:", remaining)
    print("RESULT:", "OK" if not remaining and (fix or not problems) else "FAIL")
    sys.exit(0 if not remaining and (fix or not problems) else 1)


if __name__ == "__main__":
    main()
