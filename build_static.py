"""
build_static.py — assemble a self-contained index.html with NO external requests.

Ad-blockers block generic root-level scripts (/app.js, /dashboard.js) with
net::ERR_BLOCKED_BY_CLIENT, which would silently break the deployed dashboard for some
reviewers. This inlines dashboard.js + data.json into index.html so the page fetches nothing.

Sources: index.template.html (shell) + dashboard.js (logic) + data.json (emitted by analyze.py).
Run after analyze.py:  python build_static.py
"""
from __future__ import annotations


def _guard(s: str) -> str:
    # stop a stray "</script>" inside inlined JS/JSON from closing the tag early
    return s.replace("</script", "<\\/script")


def build() -> None:
    tpl = open("index.template.html", encoding="utf-8").read()
    js = open("dashboard.js", encoding="utf-8").read()
    data = open("data.json", encoding="utf-8").read()

    html = tpl.replace('<script src="dashboard.js">__SCRIPT__</script>',
                       "<script>\n" + _guard(js) + "\n</script>")
    html = html.replace("__DATA__", _guard(data))
    assert "__SCRIPT__" not in html and "__DATA__" not in html, "placeholder left unfilled"

    open("index.html", "w", encoding="utf-8").write(html)
    print(f"built index.html ({len(html):,} chars) — dashboard.js + data.json inlined, 0 external requests")


if __name__ == "__main__":
    build()
