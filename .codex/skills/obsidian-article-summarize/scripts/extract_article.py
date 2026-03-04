#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urljoin
from urllib.request import Request, urlopen


AUTHOR_META_KEYS = {
    "author",
    "article:author",
    "twitter:creator",
    "og:article:author",
}

BLOCK_TAGS = {
    "article",
    "aside",
    "blockquote",
    "br",
    "code",
    "dd",
    "div",
    "dl",
    "dt",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "tr",
    "ul",
}


class ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.author: str | None = None
        self.images: list[dict[str, str]] = []
        self.text_parts: list[str] = []
        self.in_title = False
        self.ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()

        if tag in {"script", "style", "noscript", "svg"}:
            self.ignore_depth += 1
            return

        if tag == "title":
            self.in_title = True
            return

        if tag == "meta":
            meta_name = (attr_map.get("name") or attr_map.get("property") or "").lower()
            content = attr_map.get("content", "").strip()
            if meta_name in AUTHOR_META_KEYS and content and not self.author:
                self.author = content
            return

        if tag == "img":
            src = attr_map.get("src", "").strip()
            alt = attr_map.get("alt", "").strip()
            if src and not src.startswith("data:"):
                self.images.append({"src": src, "alt": alt})
            return

        if self.ignore_depth == 0 and tag in BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self.ignore_depth > 0:
            self.ignore_depth -= 1
            return
        if tag == "title":
            self.in_title = False
            return
        if self.ignore_depth == 0 and tag in BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignore_depth > 0:
            return
        text = unescape(data or "").strip()
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
            return
        self.text_parts.append(text + " ")

    def parsed_title(self) -> str:
        return normalize_space(" ".join(self.title_parts))

    def parsed_content(self) -> str:
        raw = "".join(self.text_parts)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        lines = [normalize_space(line) for line in raw.splitlines()]
        lines = [line for line in lines if line]
        return "\n\n".join(lines)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def author_from_html(html: str) -> str | None:
    patterns = [
        r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']article:author["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:creator["\'][^>]+content=["\']([^"\']+)["\']',
        r'(?is)<[^>]*(?:class|rel|itemprop)=["\'][^"\']*(?:author|byline)[^"\']*["\'][^>]*>([^<]{2,120})<',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            candidate = normalize_space(unescape(match.group(1)))
            if candidate:
                return candidate
    return None


def unique_image_urls(base_url: str, images: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in images:
        src = item.get("src", "").strip()
        if not src:
            continue
        abs_src = urljoin(base_url, src)
        if abs_src in seen:
            continue
        seen.add(abs_src)
        out.append({"src": abs_src, "alt": item.get("alt", "").strip()})
    return out


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
        },
    )
    with urlopen(req, timeout=45) as response:  # noqa: S310
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read()
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def extract_article(url: str) -> dict[str, object]:
    html = fetch_html(url)
    parser = ArticleParser()
    parser.feed(html)

    title = parser.parsed_title()
    author = parser.author or author_from_html(html) or ""
    content = parser.parsed_content()
    images = unique_image_urls(url, parser.images)

    if not content or len(content) < 200:
        raise RuntimeError("extracted article content is too short or empty")

    if len(content) > 120_000:
        content = content[:120_000] + "\n\n[...TRUNCATED FOR PROCESSING LIMIT...]"

    return {
        "title": title,
        "author": author,
        "content": content,
        "images": images,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python3 extract_article.py <url>"}))
        return 1

    url = sys.argv[1].strip()
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        print(json.dumps({"error": "URL must start with http:// or https://"}))
        return 1

    try:
        payload = extract_article(url)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}))
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
