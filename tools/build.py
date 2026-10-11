"""沼ろくのサポート・利用規約・プライバシーポリシーのページを作る（外部のパッケージは使わない）。

使い方:
    python3 -I tools/build.py            # 下書き。埋まっていない【要記入】を黄色で目立たせ、上に「下書き」の帯を出す
    python3 -I tools/build.py --release  # 公開用。【要記入】【確認事項】が1つでも残っていたら作らずに止める

原稿:
    利用規約・プライバシーポリシー … ../oshikatsu/legal の下書き（原稿はそちらだけに置き、ここには写さない）
    サポート                       … src/support.md
    運営者名・問い合わせ先・制定日 … site.json（原稿の【要記入】をこの値で置き換える）
出力: index.html（サポート）・terms/index.html・privacy/index.html
    公開用は dist/、下書きは draft/ に作る（下書きを公開してしまわないよう、置き場所を分ける）
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGAL = ROOT.parent.parent / "oshikatsu" / "legal"

PAGES = [
    # (出力先, 原稿, ページの題名)
    ("index.html", ROOT / "src" / "support.md", "サポート"),
    ("terms/index.html", LEGAL / "terms_of_service_draft_20261009.md", "利用規約"),
    ("privacy/index.html", LEGAL / "privacy_policy_draft_20261009.md", "プライバシーポリシー"),
]

# site.json のキー → 原稿の【要記入】
FIELDS = {
    "operator": "【要記入：運営者の名前または屋号】",
    "contact": "【要記入：問い合わせ先（メールアドレスまたは問い合わせフォームの URL）】",
    "published": "【要記入：公開日】",
}

PENDING = re.compile(r"【(要記入|確認事項)[^】]*】")


def public_body(text: str) -> str:
    """法務の下書きは、最初の --- と最後の --- の間だけが公開する本文（前後は運営者向けのメモ）"""
    parts = re.split(r"^---\s*$", text, flags=re.M)
    return parts[1] if len(parts) >= 3 else text


def fill(text: str, values: dict) -> str:
    for key, placeholder in FIELDS.items():
        value = str(values.get(key, "")).strip()
        if value:
            text = text.replace(placeholder, value)
    return text


def inline(text: str) -> str:
    """1行の中の書式。先にエスケープしてから、太字・リンク・URL・メールアドレスだけを戻す"""
    text = html.escape(text, quote=True)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    links = []

    def keep(anchor: str) -> str:
        links.append(anchor)
        return f"\0{len(links) - 1}\0"

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: keep(f'<a href="{m.group(2)}">{m.group(1)}</a>'), text)
    text = re.sub(r"https://[^\s）)<]+", lambda m: keep(f'<a href="{m.group(0)}">{m.group(0)}</a>'), text)
    text = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", lambda m: keep(f'<a href="mailto:{m.group(0)}">{m.group(0)}</a>'), text)
    text = PENDING.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)
    return re.sub(r"\0(\d+)\0", lambda m: links[int(m.group(1))], text)


def render(markdown: str) -> tuple[str, str]:
    """使っている書式だけの小さな変換（見出し・段落・箇条書き・番号付き・1段の入れ子）。戻り値は (h1 の文字, 本文の HTML)"""
    title, out, para = "", [], []
    stack: list[str] = []  # 開いているリスト（"ul" / "ol"）

    def close_para():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    def close_lists(depth: int = 0):
        while len(stack) > depth:
            out.append(f"</li></{stack.pop()}>")

    for line in markdown.splitlines():
        heading = re.match(r"^(#{1,3})\s+(.*)", line)
        item = re.match(r"^(\s*)(-|\d+\.)\s+(.*)", line)
        if heading:
            close_para()
            close_lists()
            level = len(heading.group(1))
            if level == 1 and not title:
                title = heading.group(2)
                continue
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif item:
            close_para()
            depth = 1 if len(item.group(1)) < 2 else 2
            kind = "ul" if item.group(2) == "-" else "ol"
            if len(stack) < depth:
                out.append(f"<{kind}><li>")
                stack.append(kind)
            else:
                close_lists(depth)
                out.append("</li><li>")
            out.append(inline(item.group(3)))
        elif not line.strip():
            close_para()
        else:
            close_lists()
            para.append(line.strip())
    close_para()
    close_lists()
    return title, "\n".join(out)


STYLE = """
:root{--bg:#f7f5fb;--surface:#fff;--text:#1d1b26;--muted:#5d5870;--accent:#c23a73;--line:#e3dfeb;--mark:#fff1a8}
@media (prefers-color-scheme:dark){:root{--bg:#121628;--surface:#1c1f36;--text:#ece9f5;--muted:#a9a4bd;--accent:#ff8fbd;--line:#2f3352;--mark:#6b5a00}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.8 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Hiragino Kaku Gothic ProN",sans-serif;-webkit-text-size-adjust:100%}
header{background:linear-gradient(135deg,#2a1f4f,#121628);color:#fff;padding:20px 16px}
header a{color:#fff;text-decoration:none;font-weight:700;font-size:18px}
nav{max-width:720px;margin:0 auto;display:flex;gap:16px;flex-wrap:wrap;align-items:baseline}
nav .links{display:flex;gap:14px;font-size:14px}nav .links a{font-weight:400;font-size:14px;opacity:.85}
main{max-width:720px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:26px;line-height:1.4;margin:0 0 20px}
h2{font-size:19px;margin:32px 0 8px;padding-top:16px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 4px}
p,li{overflow-wrap:anywhere}
ul,ol{padding-left:1.4em}
a{color:var(--accent)}
mark{background:var(--mark);color:inherit;padding:0 2px}
.draft{background:#fff1a8;color:#3d3300;padding:10px 16px;text-align:center;font-weight:700;font-size:14px}
footer{max-width:720px;margin:0 auto;padding:0 16px 32px;color:var(--muted);font-size:13px}
"""


def page(title: str, body: str, depth: int, draft: bool) -> str:
    up = "../" * depth or "./"
    banner = '<div class="draft">下書き：公開前に黄色の箇所を埋めてください</div>' if draft else ""
    robots = '<meta name="robots" content="noindex">' if draft else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self'">
<meta name="referrer" content="no-referrer">
{robots}
<title>{html.escape(title)}｜沼ろく</title>
<style>{STYLE}</style>
</head>
<body>
{banner}
<header><nav><a href="{up}">沼ろく</a><span class="links"><a href="{up}">サポート</a><a href="{up}terms/">利用規約</a><a href="{up}privacy/">プライバシーポリシー</a></span></nav></header>
<main>
<h1>{html.escape(title)}</h1>
{body}
</main>
<footer>沼ろく — 推し活の支出記録</footer>
</body>
</html>
"""


def main() -> int:
    release = "--release" in sys.argv[1:]
    dist = ROOT / ("dist" if release else "draft")
    values = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    problems = []
    for target, source, fallback in PAGES:
        text = source.read_text(encoding="utf-8")
        text = fill(public_body(text) if source.parent == LEGAL else text, values)
        left = sorted({m.group(0) for m in PENDING.finditer(text)})
        problems += [f"{target}: {item}" for item in left]
        if release and left:
            continue
        # 【確認事項】は運営者向けのメモなので、下書きでも本文としては出さない（残っていることは黄色の帯で分かる）
        text = "\n".join(line for line in text.splitlines() if not line.startswith("【確認事項】"))
        title, body = render(text)
        title = title.removeprefix("沼ろく ").strip() or fallback
        out = dist / target
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(title, body, target.count("/"), draft=bool(left)), encoding="utf-8")
    for item in problems:
        print(f"未記入: {item}")
    if release and problems:
        print("公開用のページは作っていません。上の箇所を埋めてから、もう一度実行してください。")
        return 1
    print(f"{'公開用' if release else '下書き'}のページを {dist} に作りました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
