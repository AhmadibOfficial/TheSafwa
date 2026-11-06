"""Text-only editing of the approved page templates; layout stays in source control."""
from functools import lru_cache
from html import escape, unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
PAGES = json.loads((CONTENT / "pages.json").read_text(encoding="utf-8"))
BY_KEY = {Path(p["fragment"]).stem: p for p in PAGES}
BY_PATH = {p["path"]: Path(p["fragment"]).stem for p in PAGES}


class TextSlots(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer("\n", source))
        self.stack = []
        self.slots = []

    def handle_starttag(self, tag, attrs):
        if tag not in {"br", "hr", "img", "input", "meta", "link", "source"}:
            self.stack.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        # HTML entities are coalesced separately when selecting editable text.
        if not data.strip() or any(t in {"svg", "script", "style", "a", "button"} for t, _ in self.stack):
            return
        labels = {"h1": "Main heading", "h2": "Section heading", "h3": "Subheading",
                  "p": "Paragraph", "figcaption": "Image caption"}
        scope = next((labels[t] if t in labels else "Purpose statement"
                      for t, a in reversed(self.stack)
                      if t in labels or a.get("role") == "tabpanel"), None)
        if scope:
            line, column = self.getpos()
            start = self.lines[line - 1] + column
            end = start + len(data)
            # Include adjacent character/entity references in this text node.
            while end < len(self.source) and self.source[end] != "<":
                end += 1
            if self.slots and start < self.slots[-1]["end"]:
                return
            original = self.source[start:end]
            text = " ".join(unescape(original).split())
            if text:
                self.slots.append({"key": f"block_{len(self.slots) + 1}", "label": scope,
                                   "text": text, "start": start, "end": end, "original": original})

    def handle_entityref(self, name):
        self.handle_data("&" + name + ";")

    def handle_charref(self, name):
        self.handle_data("&#" + name + ";")


@lru_cache(maxsize=16)
def template(key):
    source = (CONTENT / "pages" / BY_KEY[key]["fragment"]).read_text(encoding="utf-8")
    parser = TextSlots(source)
    parser.feed(source)
    return source, parser.slots


def defaults(key):
    return {slot["key"]: slot["text"] for slot in template(key)[1]}


def render_body(key, blocks):
    source, slots = template(key)
    for slot in reversed(slots):
        value = blocks.get(slot["key"], slot["text"])
        replacement = slot["original"] if value == slot["text"] else escape(value)
        source = source[:slot["start"]] + replacement + source[slot["end"]:]
    return source


def arm_for(key):
    return "institute" if key == "institute" else "studios" if key in {"studios", "quran"} else "parent"
