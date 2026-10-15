"""沼ろくの紹介ページ・サポート・利用規約・プライバシーポリシー・特商法の表記のページを作る（外部のパッケージは使わない）。

使い方:
    python3 -I tools/build.py            # 下書き。埋まっていない【要記入】を黄色で目立たせ、上に「下書き」の帯を出す
    python3 -I tools/build.py --release  # 公開用。未記入・内部メモ・許していないリンク・検査に通らないものが1つでもあれば作らずに止める

原稿:
    紹介ページ                     … src/landing.html（{{キー}} に site.json の値を差し込む）・src/landing_features.json（機能の一覧）
                                     よくある質問は site.json の landing_faq に挙げた見出しを src/support.md から切り出す
    利用規約・プライバシーポリシー … ../../oshikatsu/legal の下書き（原稿はそちらだけに置き、ここには写さない）
    サポート・特定商取引法の表記   … src/support.md・src/tokushoho.md
    画像                           … src/assets/（tools/make_images.sh で作る。公開してよいものだけ）。メタデータを消して assets/ へ写す
    運営者名・問い合わせ先・料金など … site.json
出力: index.html（紹介ページ）・support/・terms/・privacy/・tokushoho/ の index.html・assets/
    公開用は docs/（GitHub Pages が公開するフォルダ）、下書きは draft/ に作る（下書きを公開してしまわないよう、置き場所を分ける）
    1.0 のアプリと App Store Connect のサポート URL はトップを開くので、トップには常にサポートと問い合わせ先を置く（紹介ページの #contact）
    terms/・privacy/・tokushoho/ のパスはアプリが固定で持っているので、変えない
"""
from __future__ import annotations

import html
import json
import re
import struct
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGAL = ROOT.parent.parent / "oshikatsu" / "legal"
ASSETS = ROOT / "src" / "assets"

PAGES = [
    # (出力先, 原稿, ページの題名)。紹介ページ（index.html）は別に作る
    ("support/index.html", ROOT / "src" / "support.md", "サポート"),
    ("terms/index.html", LEGAL / "terms_of_service_draft_20261009.md", "利用規約"),
    ("privacy/index.html", LEGAL / "privacy_policy_draft_20261009.md", "プライバシーポリシー"),
    ("tokushoho/index.html", ROOT / "src" / "tokushoho.md", "特定商取引法に基づく表記"),
]

# すべてのページに同じものを入れる（--release で一字一句同じかを確かめる）
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; form-action 'none'"
# 外部のリンク先として許すホスト（これ以外の https は止める）
ALLOWED_HOSTS = {"apps.apple.com", "reportaproblem.apple.com", "www.apple.com", "kainan0880jwr.github.io", "docs.github.com"}
# docs/ に置いてよいファイルの種類
ALLOWED_SUFFIXES = {".html", ".png", ".jpg"}

# site.json のキー → 原稿の【要記入】
FIELDS = {
    "operator": "【要記入：運営者の名前または屋号】",
    "contact": "【要記入：問い合わせ先（メールアドレスまたは問い合わせフォームの URL）】",
    "published": "【要記入：公開日】",
}

PENDING = re.compile(r"【(要記入|確認事項)[^】]*】")
# 公開用で1つでも残っていたら止める印（【要記入】【確認事項】のほか、【メモ】など【】で書いた運営者向けの書き込みすべて）
UNRESOLVED = re.compile(r"【[^】]*】|TODO|要確認")
# リンク先として許すもの（https・メール・同じサイトの中の相対パス）
SAFE_HREF = re.compile(r"^(https://|mailto:|(?![a-zA-Z][a-zA-Z0-9+.-]*:)[\w./#-]*$)")
APP_STORE_URL = re.compile(r"^https://apps\.apple\.com/jp/app/id[0-9]+$")
EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


class BuildError(Exception):
    """公開してはいけない状態。ページを作らずに止める"""


def public_body(text: str, name: str) -> str:
    """法務の下書きは、1つ目と2つ目の --- の間だけが公開する本文（前後は運営者向けのメモ）。
    区切りがちょうど2つでなければ止める（区切りを消したり本文に --- を足したりしたときに、メモまで公開しないため）"""
    parts = re.split(r"^---\s*$", text, flags=re.M)
    if len(parts) != 3:
        raise BuildError(f"{name}: 公開する本文の区切り（--- の行）がちょうど2つではありません（{len(parts) - 1} 個）")
    return parts[1]


def fill(text: str, values: dict) -> str:
    for key, placeholder in FIELDS.items():
        value = str(values.get(key, "")).strip()
        if value:
            text = text.replace(placeholder, value)
    return text


def inline(text: str, up: str = "") -> str:
    """1行の中の書式。先にエスケープしてから、太字・リンク・URL・メールアドレスだけを戻す。
    原稿の相対リンクはサイトのトップからの位置で書く（terms/ など）。ページの深さに合わせて up（../）を前に付ける"""
    text = html.escape(text, quote=True)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    links = []

    def keep(anchor: str) -> str:
        links.append(anchor)
        return f"\0{len(links) - 1}\0"

    def link(m: re.Match) -> str:
        href = html.unescape(m.group(2))
        if not SAFE_HREF.match(href):
            raise BuildError(f"許していないリンク先です: {href}")
        if not re.match(r"^(https://|mailto:|#)", href):
            href = up + href
        return keep(f'<a href="{html.escape(href, quote=True)}">{m.group(1)}</a>')

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"https://[^\s）)<]+", lambda m: keep(f'<a href="{m.group(0)}">{m.group(0)}</a>'), text)
    text = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", lambda m: keep(f'<a href="mailto:{m.group(0)}">{m.group(0)}</a>'), text)
    text = PENDING.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)
    return re.sub(r"\0(\d+)\0", lambda m: links[int(m.group(1))], text)


def render(markdown: str, up: str = "") -> tuple[str, str]:
    """使っている書式だけの小さな変換（見出し・段落・箇条書き・番号付き・1段の入れ子）。戻り値は (h1 の文字, 本文の HTML)"""
    title, out, para = "", [], []
    stack: list[str] = []  # 開いているリスト（"ul" / "ol"）

    def close_para():
        if para:
            out.append(f"<p>{inline(' '.join(para), up)}</p>")
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
            out.append(f"<h{level}>{inline(heading.group(2), up)}</h{level}>")
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
            out.append(inline(item.group(3), up))
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
nav .links{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:14px}nav .links a{font-weight:400;font-size:14px;opacity:.85}
main{max-width:720px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:26px;line-height:1.4;margin:0 0 20px}
h2{font-size:19px;margin:32px 0 8px;padding-top:16px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 4px}
p,li{overflow-wrap:anywhere}
ul,ol{padding-left:1.4em}
a{color:var(--accent)}
a:focus-visible{outline:3px solid var(--accent);outline-offset:2px;border-radius:4px}
mark{background:var(--mark);color:inherit;padding:0 2px}
.draft{background:#fff1a8;color:#3d3300;padding:10px 16px;text-align:center;font-weight:700;font-size:14px}
footer{max-width:720px;margin:0 auto;padding:0 16px 32px;color:var(--muted);font-size:13px}
"""

LANDING_STYLE = """
:root{--bg:#f7f5fb;--band:#fff;--text:#1d1b26;--muted:#5d5870;--accent:#c23a73;--pink:#FF6FA3;--line:#e3dfeb;--card:#fff;--navy1:#2a1f4f;--navy2:#121628;--shadow:0 10px 30px rgba(42,31,79,.12)}
@media (prefers-color-scheme:dark){:root{--bg:#121628;--band:#1a1e36;--text:#ece9f5;--muted:#b3aec7;--accent:#ff8fbd;--line:#2f3352;--card:#1f2340;--navy1:#1c1538;--navy2:#0b0e1c;--shadow:0 10px 30px rgba(0,0,0,.35)}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.8 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Hiragino Kaku Gothic ProN",sans-serif}
img{max-width:100%;height:auto;display:block}
a{color:var(--accent)}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px;border-radius:8px}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px}
.narrow{max-width:760px}
.nb{display:inline-block}
.skip{position:absolute;left:-9999px;top:8px;background:#fff;color:#1d1b26;padding:8px 14px;border-radius:8px;z-index:20}
.skip:focus{left:8px}
p,li{overflow-wrap:anywhere}
/* ヘッダー */
.site-header{position:sticky;top:0;z-index:10;background:rgba(18,22,40,.94);color:#fff}
@supports (backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px)){.site-header{background:rgba(18,22,40,.7);-webkit-backdrop-filter:saturate(1.4) blur(16px);backdrop-filter:saturate(1.4) blur(16px)}}
.header-inner{display:flex;align-items:center;justify-content:space-between;height:56px}
.brand{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none;font-weight:800;font-size:19px}
.brand img{border-radius:9px}
.header-nav{display:flex;align-items:center;gap:20px;font-size:14px}
.header-nav a{color:rgba(255,255,255,.88);text-decoration:none}
.header-nav a:hover{color:#fff}
.header-nav .nav-support{background:#fff;color:#1d1b26;padding:7px 14px;border-radius:999px;font-weight:700;min-height:36px;display:inline-flex;align-items:center}
.header-nav .nav-support:focus-visible{outline-color:#ff8fbd}
.support-band{background:#fff1f6;color:#5a1e3b;font-size:14px;padding:9px 0;line-height:1.6}
.support-band a{color:#a8285f;font-weight:700}
@media (prefers-color-scheme:dark){.support-band{background:#2a1830;color:#f7d9e6}.support-band a{color:#ff9cc6}}
/* ヒーロー */
.hero{position:relative;overflow:hidden;background:linear-gradient(150deg,var(--navy1),var(--navy2) 70%);color:#fff;padding:56px 0 0}
.glow{position:absolute;inset:0;pointer-events:none;background:radial-gradient(420px 320px at 12% 18%,rgba(255,111,163,.32),transparent 70%),radial-gradient(460px 360px at 88% 30%,rgba(74,144,226,.28),transparent 70%),radial-gradient(420px 300px at 55% 100%,rgba(155,107,255,.30),transparent 70%)}
@media (prefers-reduced-motion:no-preference){.glow{animation:glow 9s ease-in-out infinite alternate}@keyframes glow{from{opacity:.75}to{opacity:1}}}
.hero-inner{position:relative;display:grid;gap:40px;align-items:center}
.eyebrow{display:inline-block;margin:0 0 14px;padding:4px 12px;border:1px solid rgba(255,255,255,.28);border-radius:999px;font-size:13px;color:rgba(255,255,255,.9);letter-spacing:.04em}
.eyebrow span{margin:0 6px;opacity:.6}
.hero h1{margin:0 0 18px;font-size:clamp(32px,7.6vw,56px);line-height:1.28;letter-spacing:.02em;font-weight:800;text-wrap:balance}
.lead{margin:0 0 26px;font-size:clamp(15px,2.2vw,18px);color:rgba(255,255,255,.86);max-width:34em}
.cta-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px 18px}
.soon{display:inline-flex;align-items:center;gap:8px;margin:0;padding:12px 20px;border:1.5px dashed rgba(255,255,255,.55);border-radius:14px;font-weight:700;color:#fff;cursor:default}
.final .soon{border-color:rgba(255,255,255,.55)}
.store-badge img{height:48px;width:auto}
.ghost{color:#fff;font-weight:700;text-decoration:none;padding:12px 4px}
.ghost:hover{text-decoration:underline}
.badges{list-style:none;display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0;padding:0;font-size:13px}
.badges li{padding:4px 12px;border-radius:999px;background:rgba(255,255,255,.12);color:rgba(255,255,255,.92)}
.hero-visual{position:relative;height:clamp(380px,112vw,520px);display:flex;justify-content:center}
.phone{position:absolute;border-radius:38px;padding:8px;background:#0e0f1a;box-shadow:0 30px 60px rgba(0,0,0,.45),0 0 0 1px rgba(255,255,255,.08)}
.phone img{border-radius:30px}
.phone-front{width:min(68vw,270px);top:0;z-index:2}
.phone-back{width:220px;top:56px;opacity:.95}
.phone-left{transform:translateX(-170px) rotate(-5deg)}
.phone-right{transform:translateX(170px) rotate(5deg)}
.only-wide{display:none}
@media (min-width:900px){
  .hero{padding:72px 0 0}
  .hero-inner{grid-template-columns:1.05fr 1fr}
  .hero-visual{height:560px}
  .only-wide{display:block}
  .header-nav .only-wide{display:inline}
}
@media (min-width:900px){@media (prefers-reduced-motion:no-preference){.phone-front{transition:transform .3s}.hero-visual:hover .phone-front{transform:translateY(-4px)}}}
/* セクション */
.section{padding:72px 0;border-top:1px solid var(--line)}
.section-title{margin:0 0 14px;font-size:clamp(24px,4.6vw,34px);line-height:1.35;text-align:center;font-weight:800;text-wrap:balance}
.section-lead{margin:0 auto 32px;max-width:40em;text-align:center;color:var(--muted)}
.cards{list-style:none;margin:28px 0 0;padding:0;display:grid;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:22px;box-shadow:var(--shadow)}
.card h3{margin:0 0 6px;font-size:17px;line-height:1.5}
.card p{margin:0;color:var(--muted);font-size:15px}
.card-icon{display:inline-grid;place-items:center;width:40px;height:40px;margin-bottom:10px;border-radius:12px;background:linear-gradient(135deg,#ff8fbd,#9b6bff);color:#fff;font-weight:800}
@media (min-width:760px){.three{grid-template-columns:repeat(3,1fr)}.two{grid-template-columns:repeat(2,1fr)}}
.steps{list-style:none;display:flex;flex-wrap:wrap;justify-content:center;gap:10px 28px;margin:32px 0 0;padding:0;font-weight:700}
.steps li{display:flex;align-items:center;gap:10px}
.step-no{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--accent);color:#fff;font-size:14px}
/* 機能 */
.feature{display:grid;gap:28px;align-items:center;padding:36px 0}
.feature + .feature{border-top:1px dashed var(--line)}
.feature-shot{justify-self:center;order:2;width:min(62vw,240px);border-radius:36px;padding:8px;background:#0e0f1a;box-shadow:var(--shadow)}
.feature-shot img{border-radius:28px}
.feature-label{margin:0 0 6px;color:var(--accent);font-weight:800;font-size:13px;letter-spacing:.08em}
.feature h3{margin:0 0 10px;font-size:clamp(22px,4vw,30px);line-height:1.4;text-wrap:balance}
.feature-lead{margin:0 0 14px;color:var(--muted)}
.points{margin:0;padding:0;list-style:none;display:grid;gap:10px}
.points li{position:relative;padding-left:26px}
.points li::before{content:"";position:absolute;left:4px;top:.62em;width:10px;height:10px;border-radius:50%;background:var(--pink)}
.premium{display:inline-block;margin-left:6px;padding:0 8px;border-radius:6px;background:#2a1f4f;color:#fff;font-size:13px;font-weight:700;line-height:1.7;vertical-align:1px}
@media (prefers-color-scheme:dark){.premium{background:#ff8fbd;color:#1d1b26}}
@media (min-width:860px){.feature{grid-template-columns:300px 1fr;gap:56px}.feature:nth-of-type(even){grid-template-columns:1fr 300px}.feature-shot{order:0}.feature:nth-of-type(even) .feature-shot{order:2}}
.mini-features{margin:24px 0 40px}.mini-feature h3{font-size:20px}.mini-feature>p:not(.feature-label){margin:0 0 12px}.mini-feature .points{font-size:15px}
.swatches{list-style:none;display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 0;padding:0;font-size:13px}
.swatches li{display:flex;align-items:center;gap:8px;padding:6px 12px 6px 6px;border-radius:999px;background:var(--card);border:1px solid var(--line)}
.swatches li::before{content:"";width:20px;height:20px;border-radius:50%;background:var(--c)}
/* 安心 */
.trust{background:linear-gradient(160deg,var(--navy1),var(--navy2));color:#fff;border-top:0}
.trust .card.dark{background:rgba(255,255,255,.07);border-color:rgba(255,255,255,.14);box-shadow:none}
.trust .card.dark p{color:rgba(255,255,255,.8)}
/* 料金 */
.free-box{max-width:760px;margin:0 auto 36px;padding:24px;border-radius:22px;background:var(--card);border:2px solid var(--accent);text-align:center}
.free-title{margin:0 0 6px;font-size:22px;font-weight:800}
.free-box p{margin:0}
.plans-title{text-align:center;font-size:22px;margin:0 0 8px}
.plans{list-style:none;margin:0;padding:0;display:grid;gap:16px}
@media (min-width:860px){.plans{grid-template-columns:repeat(3,1fr);align-items:stretch}}
.plan{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:22px;box-shadow:var(--shadow)}
.plan-featured{border:2px solid var(--accent)}
.plan-name{margin:0;font-weight:800;color:var(--muted)}
.plan-price{margin:4px 0 8px;font-size:30px;font-weight:800;line-height:1.3}
.plan-price span{font-size:14px;font-weight:600;color:var(--muted)}
.plan-note,.plan-trial{margin:0 0 8px;font-size:15px}
.plan-trial{padding:12px;border-radius:12px;background:var(--bg)}
.terms-box{max-width:860px;margin:28px auto 0;font-size:14px;color:var(--muted)}
.terms-box ul{padding-left:1.3em;margin:8px 0}
.legal-links{display:flex;flex-wrap:wrap;gap:6px 18px}
/* よくある質問 */
.faq details{border:1px solid var(--line);border-radius:16px;background:var(--card);margin:0 0 12px}
.faq summary{list-style:none;cursor:pointer;padding:16px 48px 16px 18px;font-weight:700;position:relative;min-height:44px}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"＋";position:absolute;right:18px;top:15px;color:var(--accent);font-weight:800}
.faq details[open] summary::after{content:"－"}
.faq .answer{padding:0 18px 16px;color:var(--muted)}
.faq .answer p{margin:0 0 8px}
.more{text-align:center;margin:24px 0 0;font-weight:700}
/* 最後の呼びかけ */
.final{position:relative;overflow:hidden;background:linear-gradient(150deg,var(--navy1),var(--navy2));color:#fff;padding:72px 0;text-align:center}
.final-inner{position:relative;display:flex;flex-direction:column;align-items:center;gap:14px}
.final img{border-radius:22px;box-shadow:0 14px 34px rgba(0,0,0,.35)}
.final h2{margin:6px 0 0;font-size:clamp(24px,5vw,36px)}
.final p{margin:0;color:rgba(255,255,255,.82);max-width:32em}
/* 問い合わせ */
.contact{text-align:center}
.mail{font-size:20px;font-weight:800;margin:8px 0}
.small{font-size:14px;color:var(--muted)}
/* フッター */
.site-footer{background:var(--navy2);color:rgba(255,255,255,.78);padding:40px 0;font-size:13px}
.site-footer a{color:#fff}
.footer-links{display:flex;flex-wrap:wrap;gap:8px 20px;margin:0 0 16px;padding:0;list-style:none;font-size:14px}
.site-footer p{margin:0 0 8px}
"""


def head(title: str, depth: int, draft: bool, style: str, extra: str = "") -> str:
    robots = '<meta name="robots" content="noindex">' if draft else ""
    up = "../" * depth
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light dark">
{robots}
<title>{html.escape(title)}</title>
<link rel="icon" href="{up}assets/icon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{up}assets/icon-180.png">
{extra}
<style>{style}</style>
</head>
"""


def footer_html(up: str, values: dict) -> str:
    contact = values["contact"]
    return f"""<footer class="site-footer">
<div class="wrap">
<ul class="footer-links">
<li><a href="{up}support/">サポート</a></li>
<li><a href="mailto:{html.escape(contact, quote=True)}">お問い合わせ（メール）</a></li>
<li><a href="{up}terms/">利用規約</a></li>
<li><a href="{up}privacy/">プライバシーポリシー</a></li>
<li><a href="{up}tokushoho/">特定商取引法に基づく表記</a></li>
</ul>
<p>Apple、Apple のロゴ、App Store、iPhone、iCloud、Face ID、Touch ID は、米国およびその他の国で登録された Apple Inc. の商標です。App Store は Apple Inc. のサービスマークです。iPhone の商標は、アイホン株式会社のライセンスにもとづき使用されています。</p>
<p>{html.escape(values.get("copyright", ""))}</p>
</div>
</footer>"""


def page(title: str, body: str, depth: int, draft: bool, values: dict) -> str:
    """サポート・規約などの、文章のページ"""
    up = "../" * depth or "./"
    banner = '<div class="draft">下書き：公開前に黄色の箇所を埋めてください</div>' if draft else ""
    return head(f"{title}｜沼ろく", depth, draft, STYLE) + f"""<body>
{banner}
<header><nav><a href="{up}">沼ろく</a><span class="links"><a href="{up}support/">サポート</a><a href="{up}terms/">利用規約</a><a href="{up}privacy/">プライバシーポリシー</a><a href="{up}tokushoho/">特定商取引法に基づく表記</a></span></nav></header>
<main>
<h1>{html.escape(title)}</h1>
{body}
</main>
<footer>沼ろく — 推し活の支出記録<br>{html.escape(values.get("copyright", ""))}</footer>
</body>
</html>
"""


# ---- 紹介ページ ----

def fill_template(template: str, text_values: dict, html_values: dict) -> str:
    """{{キー}} は文字として（エスケープして）、{{{キー}}} は検査済みの HTML の断片として差し込む。
    知らないキーや、差し込みの残りがあれば止める（str.format は CSS の {} とぶつかるので使わない）"""
    def raw(m: re.Match) -> str:
        key = m.group(1)
        if key not in html_values:
            raise BuildError(f"紹介ページ：決めていない差し込み {{{{{{{key}}}}}}}")
        return html_values[key]

    def text(m: re.Match) -> str:
        key = m.group(1)
        if key not in text_values:
            raise BuildError(f"紹介ページ：決めていない差し込み {{{{{key}}}}}")
        return html.escape(str(text_values[key]), quote=True)

    out = re.sub(r"\{\{\{\s*([a-z0-9_]+)\s*\}\}\}", raw, template)
    out = re.sub(r"\{\{\s*([a-z0-9_]+)\s*\}\}", text, out)
    if "{{" in out or "}}" in out:
        raise BuildError("紹介ページ：差し込みの書き方が崩れています（{{ が残っています）")
    return out


def features_html(features: list) -> str:
    """画像のある機能は左右交互の大きな並び、画像のない機能（image が空）は最後にカードとして並べる"""
    out, cards = [], []
    for f in features:
        points = []
        for p in f["points"]:
            label = f'<span class="premium">{html.escape(p["premium"])}</span>' if p.get("premium") else ""
            points.append(f"<li>{html.escape(p['text'])}{label}</li>")
        if not f.get("image"):
            cards.append(f"""<li class="card mini-feature" id="feature-{html.escape(f['id'], quote=True)}">
<p class="feature-label">{html.escape(f['eyebrow'])}</p>
<h3>{html.escape(f['title'])}</h3>
<p>{html.escape(f['lead'])}</p>
<ul class="points">{''.join(points)}</ul>
</li>""")
            continue
        image = html.escape(f["image"], quote=True)
        out.append(f"""<article class="feature" id="feature-{html.escape(f['id'], quote=True)}">
<div class="feature-shot"><img src="assets/screen-{image}-320.jpg" srcset="assets/screen-{image}-320.jpg 320w, assets/screen-{image}-640.jpg 640w" sizes="(min-width: 860px) 284px, min(62vw, 224px)" width="320" height="695" alt="{html.escape(f['alt'], quote=True)}" loading="lazy" decoding="async"></div>
<div class="feature-copy">
<p class="feature-label">{html.escape(f['eyebrow'])}</p>
<h3>{html.escape(f['title'])}</h3>
<p class="feature-lead">{html.escape(f['lead'])}</p>
<ul class="points">{''.join(points)}</ul>{swatches_html(f.get("swatches"))}
</div>
</article>""")
    if cards:
        out.append(f'<ul class="cards two mini-features">{"".join(cards)}</ul>')
    return "\n".join(out)


def swatches_html(swatches) -> str:
    """推し色の見本（色の値は #RRGGBB だけを許す）"""
    if not swatches:
        return ""
    items = []
    for name, color in swatches:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
            raise BuildError(f"推し色の見本の色の形が正しくありません: {color}")
        items.append(f'<li style="--c:{color}">{html.escape(name)}</li>')
    return f'\n<ul class="swatches" aria-label="選べる推し色（12色）の一部">{"".join(items)}</ul>'


def faq_html(questions: list, support_text: str) -> str:
    """サポートの原稿から、挙げた見出しの節（### 見出し 〜 次の見出しまで）を切り出す。見つからなければ止める"""
    out = []
    for i, question in enumerate(questions):
        m = re.search(rf"^### {re.escape(question)}\n(.*?)(?=^#{{2,3}} |\Z)", support_text, flags=re.M | re.S)
        if not m:
            raise BuildError(f"紹介ページ：サポートに「{question}」の質問が見つかりません")
        _, answer = render(m.group(1).strip(), up="")
        opened = " open" if i == 0 else ""
        out.append(f'<details{opened}><summary>{html.escape(question)}</summary><div class="answer">{answer}</div></details>')
    return "\n".join(out)


def store_cta(values: dict) -> str:
    """公開前は押せない文字の表示（バッジの形にしない・公開日を書かない）。公開後は App Store のページへのリンク"""
    app_id = str(values.get("app_store_id", "")).strip()
    if not app_id:
        return '<p class="soon"><span aria-hidden="true">✦</span> App Store で近日公開予定</p>'
    url = f"https://apps.apple.com/jp/app/id{app_id}"
    if not APP_STORE_URL.match(url):
        raise BuildError(f"site.json の app_store_id の形が正しくありません: {app_id}")
    if not (ASSETS / "app-store-badge.png").exists():
        raise BuildError("Apple 公式の App Store バッジ（src/assets/app-store-badge.png）がありません")
    return f'<a class="store-badge" href="{url}"><img src="assets/app-store-badge.png" width="150" height="48" alt="App Store からダウンロード"></a>'


def landing(values: dict, support_text: str, draft: bool) -> str:
    base = values["base_url"]
    if not base.startswith("https://kainan0880jwr.github.io/") or not base.endswith("/"):
        raise BuildError(f"site.json の base_url の形が正しくありません: {base}")
    if not EMAIL.match(values["contact"]):
        raise BuildError("site.json の contact がメールアドレスの形ではありません")
    description = "推しに使ったお金を記録して、推し全員の合計と推しごとの内訳がひと目でわかる iPhone アプリ。毎月・年間のまとめ画像でふり返り。基本無料・広告なし。"
    app_id = str(values.get("app_store_id", "")).strip()
    banner = f'<meta name="apple-itunes-app" content="app-id={html.escape(app_id, quote=True)}">' if app_id else ""
    extra = f"""<meta name="description" content="{html.escape(description, quote=True)}">
<link rel="canonical" href="{base}">
<meta property="og:type" content="website">
<meta property="og:title" content="沼ろく｜推し活の支出記録アプリ">
<meta property="og:description" content="{html.escape(description, quote=True)}">
<meta property="og:url" content="{base}">
<meta property="og:image" content="{base}assets/ogp.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#2a1f4f" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#121628" media="(prefers-color-scheme: dark)">
{banner}"""
    features = json.loads((ROOT / "src" / "landing_features.json").read_text(encoding="utf-8"))
    template = (ROOT / "src" / "landing.html").read_text(encoding="utf-8")
    text_values = {k: values[k] for k in ("price_yearly", "price_monthly", "price_lifetime", "price_as_of", "trial_days", "contact")}
    cta = store_cta(values)
    body = fill_template(template, text_values, {
        "store_cta": cta,
        "features_html": features_html(features),
        "faq_html": faq_html(values["landing_faq"], support_text),
    })
    banner_html = '<div class="draft" style="background:#fff1a8;color:#3d3300;padding:10px 16px;text-align:center;font-weight:700;font-size:14px">下書き：公開前に黄色の箇所を埋めてください</div>' if draft else ""
    return head("沼ろく｜推し活の支出記録アプリ", 0, draft, LANDING_STYLE, extra) + f"<body>\n{banner_html}\n{body}\n{footer_html('', values)}\n</body>\n</html>\n"


def check_prices(values: dict, tokushoho: str):
    """料金は特商法の表記（原稿）と一致していること。違えば止める（料金を書き換えるときは両方を同じ日に直す）"""
    for key in ("price_yearly", "price_monthly", "price_lifetime"):
        if values[key] not in tokushoho:
            raise BuildError(f"site.json の {key}（{values[key]}）が特定商取引法に基づく表記の原稿にありません")
    if values["trial_days"] not in tokushoho:
        raise BuildError(f"site.json の trial_days（{values['trial_days']}）が特定商取引法に基づく表記の原稿にありません")


# ---- 画像（メタデータを消して写す） ----

PNG_KEEP = {b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND", b"sRGB", b"gAMA"}


def strip_png(data: bytes, name: str) -> bytes:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise BuildError(f"{name}: PNG ではありません")
    out, pos = [data[:8]], 8
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos:pos + 12 + length]
        if kind in PNG_KEEP:
            out.append(chunk)
        pos += 12 + length
    return b"".join(out)


def strip_jpeg(data: bytes, name: str) -> bytes:
    """APP0（JFIF）以外の APP1〜APP15（Exif・XMP・ICC など）とコメントを落とす。画像の本体（SOS 以降）はそのまま"""
    if data[:2] != b"\xff\xd8":
        raise BuildError(f"{name}: JPEG ではありません")
    out, pos = [b"\xff\xd8"], 2
    while pos < len(data):
        if data[pos] != 0xFF:
            raise BuildError(f"{name}: JPEG の区切りが読めません")
        marker = data[pos + 1]
        if marker == 0xDA:  # SOS：ここから後ろは画像の本体
            out.append(data[pos:])
            break
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        segment = data[pos:pos + 2 + length]
        if not (0xE1 <= marker <= 0xEF or marker == 0xFE):
            out.append(segment)
        pos += 2 + length
    return b"".join(out)


def check_image(data: bytes, name: str):
    """写した後の画像に、許していない塊（メタデータ）が残っていないこと"""
    if name.endswith(".png"):
        pos = 8
        while pos < len(data):
            length, kind = struct.unpack(">I4s", data[pos:pos + 8])
            if kind not in PNG_KEEP:
                raise BuildError(f"{name}: メタデータ（{kind.decode(errors='replace')}）が残っています")
            pos += 12 + length
    else:
        pos = 2
        while pos < len(data) and data[pos + 1] != 0xDA:
            marker = data[pos + 1]
            if 0xE1 <= marker <= 0xEF or marker == 0xFE:
                raise BuildError(f"{name}: メタデータ（APP{marker - 0xE0}）が残っています")
            pos += 2 + struct.unpack(">H", data[pos + 2:pos + 4])[0]


def assets() -> dict[str, bytes]:
    out = {}
    for path in sorted(ASSETS.iterdir()):
        if path.name.startswith("."):
            continue
        name = path.name
        if path.suffix not in {".png", ".jpg"}:
            raise BuildError(f"src/assets/{name}: PNG・JPEG 以外は置けません（SVG は公開しない）")
        if re.search(r"1\.1|iap|review|paywall", name, flags=re.I):
            raise BuildError(f"src/assets/{name}: 未公開・審査用の画像は置けません")
        data = path.read_bytes()
        data = strip_png(data, name) if path.suffix == ".png" else strip_jpeg(data, name)
        check_image(data, name)
        out[f"assets/{name}"] = data
    return out


# ---- 出力した HTML の検査 ----

class Audit(HTMLParser):
    """許していない要素・属性・リンク先・コメントを見つけたら止める（Markdown 側の検査をすり抜ける生の HTML のため）"""
    FORBIDDEN = {"script", "iframe", "object", "embed", "form", "base", "frame", "frameset", "svg"}

    def __init__(self, page_path: str, files: set[str], values: dict):
        super().__init__(convert_charrefs=True)
        self.page, self.files, self.values = page_path, files, values
        self.csp, self.in_style = None, False

    def error(self, message: str):
        raise BuildError(f"{self.page}: {message}")

    def handle_comment(self, data):
        self.error("HTML のコメントは公開しません（内部メモが残る原因になるため）")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.FORBIDDEN:
            self.error(f"<{tag}> は使えません")
        if tag == "link" and a.get("rel") == "stylesheet":
            self.error("外部の CSS は使えません")
        if tag == "meta" and a.get("http-equiv") == "Content-Security-Policy":
            self.csp = a.get("content")
        if tag == "style":
            self.in_style = True
        if a.get("target") == "_blank":
            self.error('target="_blank" は使いません')
        for key, value in attrs:
            value = value or ""
            if key.startswith("on"):
                self.error(f"{key} 属性は使えません")
            if key == "style" and re.search(r"url\(|expression|@import", value, flags=re.I):
                self.error("style 属性の中で外部を読み込めません")
            urls = []
            if key in {"href", "src"}:
                urls = [value]
            elif key == "srcset":
                urls = [part.strip().split()[0] for part in value.split(",") if part.strip()]
            elif key == "content" and a.get("property", "").startswith("og:") and a.get("property") in {"og:url", "og:image"}:
                urls = [value]
            for url in urls:
                self.check_url(url)

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style and re.search(r"url\(|@import", data, flags=re.I):
            self.error("<style> の中で外部を読み込めません")

    def check_url(self, url: str):
        if url.startswith("mailto:"):
            if url != f"mailto:{self.values['contact']}":
                self.error(f"site.json の問い合わせ先以外のメールアドレスです: {url}")
            return
        if url.startswith("#"):
            return
        if url.startswith("https://"):
            host = url.split("/")[2]
            if host not in ALLOWED_HOSTS:
                self.error(f"許していないリンク先のホストです: {host}")
            if host == "kainan0880jwr.github.io":
                if not url.startswith(self.values["base_url"]):
                    self.error(f"自分のサイト以外の github.io です: {url}")
                self.check_url(url[len(self.values["base_url"]):] or "./")
            if host == "apps.apple.com" and not APP_STORE_URL.match(url):
                self.error(f"App Store の URL の形が正しくありません: {url}")
            return
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
            self.error(f"許していないリンク先です: {url}")
        # 同じサイトの中：ページの場所から実在するファイルを確かめる
        base = self.page.rsplit("/", 1)[0] if "/" in self.page else ""
        path = url.split("#")[0]
        parts = [p for p in (base.split("/") if base else [])]
        for p in path.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if not parts:
                    self.error(f"サイトの外を指しています: {url}")
                parts.pop()
            else:
                parts.append(p)
        target = "/".join(parts)
        if path.endswith("/") or path in ("", "./") or not path:
            target = (target + "/index.html").lstrip("/")
        if target not in self.files:
            self.error(f"リンク先のファイルがありません: {url}（{target}）")


def audit(outputs: dict[str, bytes | str], values: dict):
    files = set(outputs)
    for name, content in outputs.items():
        if not name.endswith(".html"):
            continue
        checker = Audit(name, files, values)
        checker.feed(content)
        checker.close()
        if checker.csp != CSP:
            raise BuildError(f"{name}: CSP が決まったものと違います")
        if UNRESOLVED.search(re.sub(r"<[^>]+>", "", content)):
            raise BuildError(f"{name}: 【】・TODO・要確認 が残っています")
    landing_page = outputs["index.html"]
    # 1.0 のアプリはトップをサポートとして開くので、トップからサポートと問い合わせ先にすぐ行けること
    if 'href="support/"' not in landing_page or f'href="mailto:{values["contact"]}"' not in landing_page:
        raise BuildError("index.html: トップにサポートへのリンクと問い合わせ先がありません")


def main() -> int:
    release = "--release" in sys.argv[1:]
    dist = ROOT / ("docs" if release else "draft")
    values = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    outputs: dict[str, bytes | str] = {}
    problems = []
    try:
        support_text = ""
        tokushoho_text = ""
        for target, source, fallback in PAGES:
            text = source.read_text(encoding="utf-8")
            text = fill(public_body(text, source.name) if source.parent == LEGAL else text, values)
            pattern = UNRESOLVED if release else PENDING
            left = sorted({m.group(0) for m in pattern.finditer(text)})
            problems += [f"{target}: {item}" for item in left]
            # 【確認事項】は運営者向けのメモなので、下書きでも本文としては出さない（残っていることは黄色の帯で分かる）
            text = "\n".join(line for line in text.splitlines() if not line.startswith("【確認事項】"))
            if target.startswith("support/"):
                support_text = text
            if target.startswith("tokushoho/"):
                tokushoho_text = text
            depth = target.count("/")
            title, body = render(text, up="../" * depth)
            title = title.removeprefix("沼ろく ").strip() or fallback
            outputs[target] = page(title, body, depth, draft=bool(left), values=values)
        check_prices(values, tokushoho_text)
        outputs["index.html"] = landing(values, support_text, draft=bool(problems))
        outputs.update(assets())
        audit(outputs, values)
    except BuildError as error:
        print(f"止めました: {error}")
        return 1
    for item in problems:
        print(f"未解決: {item}")
    if release and problems:
        # 公開用は、全ページが問題なしの時だけ書く（一部のページだけ新しくなるのを防ぐ）
        print("公開用のページは作っていません。上の箇所を直してから、もう一度実行してください。")
        return 1
    if release:
        # 今回作らなかったファイルが docs/ に残っていたら止める（消すのは人が確かめてから）
        stale = sorted(str(p.relative_to(dist)) for p in dist.rglob("*")
                       if p.is_file() and p.name != ".nojekyll" and str(p.relative_to(dist)) not in outputs)
        odd = sorted(name for name in outputs if Path(name).suffix not in ALLOWED_SUFFIXES)
        if stale or odd:
            for name in stale:
                print(f"古いファイル: docs/{name}（今回は作っていません。確かめてから消してください）")
            for name in odd:
                print(f"置けない種類のファイル: {name}")
            print("公開用のページは作っていません。")
            return 1
    for target, content in outputs.items():
        out = dist / target
        out.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            out.write_bytes(content)
        else:
            out.write_text(content, encoding="utf-8")
    # GitHub Pages の Jekyll の変換を通さず、そのまま配信させる
    (dist / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{'公開用' if release else '下書き'}のページを {dist} に作りました（{len(outputs)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
