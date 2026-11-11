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
出力: index.html（紹介ページ）・support/・terms/・privacy/・tokushoho/ の index.html・assets/（画像と site.css・landing.css）・sitemap.xml・robots.txt
    公開用は docs/（GitHub Pages が公開するフォルダ）、下書きは draft/ に作る（下書きを公開してしまわないよう、置き場所を分ける）
    1.0 のアプリと App Store Connect のサポート URL はトップを開くので、トップには常にサポートと問い合わせ先を置く（紹介ページの #contact）
    terms/・privacy/・tokushoho/ のパスはアプリが固定で持っているので、変えない
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGAL = ROOT.parent.parent / "oshikatsu" / "legal"
ASSETS = ROOT / "src" / "assets"

PAGES = [
    # (出力先, 原稿, ページの題名)。紹介ページ（index.html）は別に作る
    ("support/index.html", ROOT / "src" / "support.md", "サポート"),
    ("terms/index.html", LEGAL / "terms_of_service_ja_v1.3_20261019.md", "利用規約"),
    ("privacy/index.html", LEGAL / "privacy_policy_ja_v1.3_20261019.md", "プライバシーポリシー"),
    ("tokushoho/index.html", ROOT / "src" / "tokushoho.md", "特定商取引法に基づく表記"),
]
# 日本語以外のページ（1.3 多言語版）。アプリはその言語の /<dir>/ の規約・ポリシー・サポートを開く（アプリの LegalLinks と同じ dir）。
# 規約・ポリシーは日本語版が正本で、ほかの言語はその訳（原稿は ../../oshikatsu/legal の *_<言語>_20261019.md）
LANGS = {
    "en": {"dir": "en", "og": "en_US", "name": "English", "tagline": "Oshi spending log", "store": "Download on the App Store",
           "support": "Support", "terms": "Terms of Use", "privacy": "Privacy Policy"},
    "de": {"dir": "de", "og": "de_DE", "name": "Deutsch", "tagline": "Oshi-Ausgabenbuch", "store": "Laden im App Store",
           "support": "Support", "terms": "Nutzungsbedingungen", "privacy": "Datenschutzerklärung"},
    "es": {"dir": "es", "og": "es_ES", "name": "Español", "tagline": "Registro de gastos de oshi", "store": "Descargar en el App Store",
           "support": "Soporte", "terms": "Términos de uso", "privacy": "Política de privacidad"},
    "fr": {"dir": "fr", "og": "fr_FR", "name": "Français", "tagline": "Carnet de dépenses d'oshi", "store": "Télécharger dans l'App Store",
           "support": "Assistance", "terms": "Conditions d'utilisation", "privacy": "Politique de confidentialité"},
    "it": {"dir": "it", "og": "it_IT", "name": "Italiano", "tagline": "Diario delle spese per gli oshi", "store": "Scarica su App Store",
           "support": "Supporto", "terms": "Termini di utilizzo", "privacy": "Informativa sulla privacy"},
    "pt-BR": {"dir": "pt-br", "og": "pt_BR", "name": "Português (Brasil)", "tagline": "Registro de gastos com oshi", "store": "Baixar na App Store",
              "support": "Suporte", "terms": "Termos de Uso", "privacy": "Política de Privacidade"},
    "tr": {"dir": "tr", "og": "tr_TR", "name": "Türkçe", "tagline": "Oshi harcama kaydı", "store": "App Store'dan İndirin",
           "support": "Destek", "terms": "Kullanım Koşulları", "privacy": "Gizlilik Politikası"},
    "hi": {"dir": "hi", "og": "hi_IN", "name": "हिन्दी", "tagline": "ओशी खर्च रिकॉर्ड", "store": "App Store से डाउनलोड करें",
           "support": "सहायता", "terms": "उपयोग की शर्तें", "privacy": "गोपनीयता नीति"},
    "vi": {"dir": "vi", "og": "vi_VN", "name": "Tiếng Việt", "tagline": "Sổ chi tiêu cho oshi", "store": "Tải về trên App Store",
           "support": "Hỗ trợ", "terms": "Điều khoản sử dụng", "privacy": "Chính sách quyền riêng tư"},
    "id": {"dir": "id", "og": "id_ID", "name": "Bahasa Indonesia", "tagline": "Catatan belanja oshi", "store": "Unduh di App Store",
           "support": "Bantuan", "terms": "Ketentuan Penggunaan", "privacy": "Kebijakan Privasi"},
}
PAGES_INTL = []
for _code, _lang in LANGS.items():
    _dir = _lang["dir"]
    PAGES_INTL += [
        (f"{_dir}/index.html", ROOT / "src" / _dir / "index.md", "Numaroku"),
        (f"{_dir}/support/index.html", ROOT / "src" / _dir / "support.md", _lang["support"]),
        (f"{_dir}/terms/index.html", LEGAL / f"terms_of_service_{_code}_20261019.md", _lang["terms"]),
        (f"{_dir}/privacy/index.html", LEGAL / f"privacy_policy_{_code}_20261019.md", _lang["privacy"]),
    ]
LANG_OF_DIR = {lang["dir"]: code for code, lang in LANGS.items()}

# すべてのページに同じものを入れる（--release で一字一句同じかを確かめる）
# CSS は同一オリジンの assets/*.css だけ（<style> と style 属性は使わない。'unsafe-inline' を入れない）
CSP = "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'"
# 外部のリンク先として許すホスト（これ以外の https は止める）
ALLOWED_HOSTS = {"apps.apple.com", "reportaproblem.apple.com", "www.apple.com", "kainan0880jwr.github.io", "docs.github.com"}
# docs/ に置いてよいファイルの種類
ALLOWED_SUFFIXES = {".html", ".png", ".jpg", ".css", ".xml", ".txt"}
# .css・.xml・.txt は、このビルドが作る決まった名前のものだけ（原稿や画像の置き場から紛れ込ませない）
GENERATED_TEXT_FILES = {"assets/site.css", "assets/landing.css", "sitemap.xml", "robots.txt"}
# CSS の中に1つでもあれば止めるもの（外部の読み込み・古い IE の式・エスケープでの書き換え）
CSS_FORBIDDEN = re.compile(r"url\(|@import|expression|(?<![\w-])behavior\s*:|-moz-binding|\\|</", flags=re.I)

# site.json のキー → 原稿の【要記入】
FIELDS = {
    "operator": "【要記入：運営者の名前または屋号】",
    "contact": "【要記入：問い合わせ先（メールアドレスまたは問い合わせフォームの URL）】",
    "published": "【要記入：公開日】",
    "operator_en": "【要記入：運営者の名前（英語）】",
    "published_en": "【要記入：公開日（英語）】",
}
# ほかの言語の公開日（運営者の名前は英語と同じ表記を使う）
FIELDS.update({f"published_{code}": f"【要記入：公開日（{code}）】" for code in LANGS if code != "en"})
# 1.10 のポリシー改定日（1.10 が App Store で公開された日に site.json の revised_1_10・revised_1_10_<言語> を書く。
# 書くまでは下書きも公開用も止まる＝公開前のポリシーを出さないための歯止め。2026-11-11 法務レビュー L-1・L-3・L-16・L-21）
FIELDS["revised_1_10"] = "【要記入：1.10 の公開日】"
FIELDS.update({f"revised_1_10_{code}": f"【要記入：1.10 の公開日（{code}）】" for code in LANGS})

PENDING = re.compile(r"【(要記入|確認事項)[^】]*】")
# 公開用で1つでも残っていたら止める印（【要記入】【確認事項】のほか、【メモ】など【】で書いた運営者向けの書き込みすべて）
UNRESOLVED = re.compile(r"【[^】]*】|TODO|要確認")
# リンク先として許すもの（https・メール・同じサイトの中の相対パス）
SAFE_HREF = re.compile(r"^(https://|mailto:|(?![a-zA-Z][a-zA-Z0-9+.-]*:)[\w./#-]*$)")
# 実装と食い違う表記（過去に直したもの）。公開物に1つでもあれば止める（2026-10-28 の専門家レビュー）
STALE_CLAIMS = ["何枚でも", "複数枚", "写真はバックアップと CSV には含まれず", "Unlimited photos", "unlimited photos", "Unbegrenzt Fotos"]
APP_STORE_URL = re.compile(r"^https://apps\.apple\.com/(jp/)?app/id[0-9]+$")
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
@media (prefers-reduced-motion:no-preference){@view-transition{navigation:auto}}
:root{--bg:#f7f5fb;--surface:#fff;--text:#1d1b26;--muted:#5d5870;--accent:#c23a73;--line:#e3dfeb;--mark:#fff1a8}
@media (prefers-color-scheme:dark){:root{--bg:#121628;--surface:#1c1f36;--text:#ece9f5;--muted:#a9a4bd;--accent:#ff8fbd;--line:#2f3352;--mark:#6b5a00}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.8 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Hiragino Kaku Gothic ProN",sans-serif;-webkit-text-size-adjust:100%}
header{background:linear-gradient(135deg,#2a1f4f,#121628);color:#fff;padding:20px 16px}
.store{margin:16px 0}.store-link{display:inline-flex;align-items:center;min-height:44px;padding:10px 20px;border-radius:12px;background:#000;color:#fff;font-weight:700;text-decoration:none}
header a{color:#fff;text-decoration:none;font-weight:700;font-size:18px}
nav{max-width:720px;margin:0 auto;display:flex;gap:16px;flex-wrap:wrap;align-items:baseline}
nav .links{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:14px}nav .links a{font-weight:400;font-size:14px;opacity:.85}
main{max-width:720px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:26px;line-height:1.4;margin:0 0 20px}
h2{font-size:19px;margin:32px 0 8px;padding-top:16px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 4px}
p,li{overflow-wrap:anywhere;text-wrap:pretty}
ul,ol{padding-left:1.4em}
a{color:var(--accent)}
a:focus-visible{outline:3px solid var(--accent);outline-offset:2px;border-radius:4px}
mark{background:var(--mark);color:inherit;padding:0 2px}
.draft{background:#fff1a8;color:#3d3300;padding:10px 16px;text-align:center;font-weight:700;font-size:14px}
footer{max-width:720px;margin:0 auto;padding:0 16px 32px;color:var(--muted);font-size:13px}
.langs{display:flex;flex-wrap:wrap;gap:4px 14px;margin:0 0 12px;padding:0;list-style:none}
"""

# 紹介ページの CSS は src/landing.css に書く（2026-11 の作り直しで build.py の外へ出した。検査は今までどおり CSS_FORBIDDEN）
LANDING_STYLE = (ROOT / "src" / "landing.css").read_text(encoding="utf-8")


def stylesheet_href(name: str, css: str, up: str = "") -> str:
    """同一オリジンの CSS へのリンク。中身が変わったらキャッシュを使わないよう、中身のハッシュを ?v= に付ける"""
    return f"{up}assets/{name}?v={hashlib.sha256(css.encode('utf-8')).hexdigest()[:10]}"


def head(title: str, depth: int, draft: bool, stylesheet: str, extra: str = "", lang: str = "ja") -> str:
    """stylesheet は stylesheet_href で作った、ページの場所から見た CSS の相対パス"""
    robots = '<meta name="robots" content="noindex">' if draft else ""
    up = "../" * depth
    return f"""<!doctype html>
<html lang="{lang}">
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
<link rel="stylesheet" href="{html.escape(stylesheet, quote=True)}">
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
<ul class="footer-links">{language_links(up)}</ul>
<p>Apple、Apple のロゴ、App Store、iPhone、iCloud、Face ID、Touch ID は、米国およびその他の国で登録された Apple Inc. の商標です。App Store は Apple Inc. のサービスマークです。iPhone の商標は、アイホン株式会社のライセンスにもとづき使用されています。</p>
<p>{html.escape(values.get("copyright", ""))}</p>
</div>
</footer>"""


def language_links(up: str) -> str:
    """すべての言語のトップへのリンク（各ページのフッター）"""
    items = [f'<li><a href="{up}" lang="ja">日本語</a></li>']
    items += [f'<li><a href="{up}{lang["dir"]}/" lang="{code}">{html.escape(lang["name"])}</a></li>' for code, lang in LANGS.items()]
    return "".join(items)


def alternates(values: dict) -> str:
    """紹介ページ（各言語のトップ）が互いに訳であることを検索エンジンに伝える"""
    base = values["base_url"]
    links = [f'<link rel="alternate" hreflang="ja" href="{base}">']
    links += [f'<link rel="alternate" hreflang="{code}" href="{base}{lang["dir"]}/">' for code, lang in LANGS.items()]
    # 日本語以外の言語の人には英語のページを（日本語の人は hreflang="ja" で日本語のページへ）
    links.append(f'<link rel="alternate" hreflang="x-default" href="{base}en/">')
    return "\n".join(links)


def app_store_url(values: dict, country: str = "") -> str:
    """国を入れない URL は、開いた人の国の App Store に移る"""
    app_id = str(values.get("app_store_id", "")).strip()
    url = f"https://apps.apple.com/{country}app/id{app_id}"
    if not app_id or not APP_STORE_URL.match(url):
        raise BuildError(f"site.json の app_store_id の形が正しくありません: {app_id}")
    return url


# OGP の画像（assets/ogp.jpg。全言語で同じ日本語の画像）の説明
OGP_ALT_JA = "沼ろくのアイコンと「推しに使ったお金、ぜんぶ思い出に。」の文字。横にホーム画面（11月に推しに使った金額 23,020円、次のイベントまで12日、見送った金額）"
OGP_ALT_EN = "Numaroku app icon with its Japanese tagline, next to the Home screen showing ¥23,020 spent on oshis in November, 12 days to the next event, and skipped purchases"


def intl_top_head(body: str, lang: str, values: dict) -> str:
    """日本語以外のトップの説明・OGP・canonical・スマートアプリバナー。説明は本文の最初の段落から作る"""
    names = LANGS[lang]
    base = f'{values["base_url"]}{names["dir"]}/'
    m = re.search(r"<p>(.*?)</p>", body, flags=re.S)
    description = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else names["tagline"]
    if len(description) > 160:
        description = description[:157].rsplit(" ", 1)[0] + "…"
    d = html.escape(description, quote=True)
    return f"""<meta name="description" content="{d}">
<link rel="canonical" href="{base}">
{alternates(values)}
<meta property="og:type" content="website">
<meta property="og:title" content="Numaroku — {html.escape(names['tagline'], quote=True)}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{base}">
<meta property="og:image" content="{values['base_url']}assets/ogp.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{html.escape(OGP_ALT_EN, quote=True)}">
<meta property="og:locale" content="{names['og']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="apple-itunes-app" content="app-id={html.escape(str(values['app_store_id']), quote=True)}">"""


def page(title: str, body: str, depth: int, draft: bool, values: dict, lang: str = "ja") -> str:
    """サポート・規約などの、文章のページ。lang が ja 以外なら、その言語のページ（/<dir>/ の下。見出し・案内・フッターもその言語）"""
    up = "../" * depth or "./"
    banner = '<div class="draft">下書き：公開前に黄色の箇所を埋めてください</div>' if draft else ""
    extra = ""
    if lang != "ja":
        names = LANGS[lang]
        base = f"{up}{names['dir']}/"
        nav = (f'<a href="{base}">Numaroku</a><span class="links"><a href="{base}support/">{html.escape(names["support"])}</a>'
               f'<a href="{base}terms/">{html.escape(names["terms"])}</a><a href="{base}privacy/">{html.escape(names["privacy"])}</a>'
               f'<a href="{up}" lang="ja">日本語</a></span>')
        footer = (f'<ul class="langs">{language_links(up)}</ul>'
                  f"Numaroku — {html.escape(names['tagline'])}<br>{html.escape(values.get('copyright', ''))}")
        page_title = title if title == "Numaroku" else f"{title} | Numaroku"
        if title == "Numaroku":
            extra = intl_top_head(body, lang, values)
            store = f'<p class="store"><a class="store-link" href="{app_store_url(values)}">{html.escape(names["store"])}</a></p>'
            body = re.sub(r"(<p>.*?</p>)", lambda m: m.group(1) + "\n" + store, body, count=1, flags=re.S) + "\n" + store
    else:
        nav = (f'<a href="{up}">沼ろく</a><span class="links"><a href="{up}support/">サポート</a><a href="{up}terms/">利用規約</a>'
               f'<a href="{up}privacy/">プライバシーポリシー</a><a href="{up}tokushoho/">特定商取引法に基づく表記</a>'
               f'<a href="{up}en/" lang="en">English</a></span>')
        footer = f'<ul class="langs">{language_links(up)}</ul>沼ろく — 推し活の支出記録<br>{html.escape(values.get("copyright", ""))}'
        page_title = f"{title}｜沼ろく"
    return head(page_title, depth, draft, stylesheet_href("site.css", site_css(), "../" * depth), extra, lang=lang) + f"""<body>
{banner}
<header><nav>{nav}</nav></header>
<main>
<h1>{html.escape(title)}</h1>
{body}
</main>
<footer>{footer}</footer>
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
    """「ほかにも」の格子（src/landing_features.json）。主役の機能は landing.html に直接書く。
    プレミアムの部分は札ではなく ✦ の印と短い文で添える（無料で使えるものを主役にするため）"""
    items = []
    for f in features:
        for key in ("id", "title", "text"):
            if not f.get(key):
                raise BuildError(f"landing_features.json: {key} がありません: {f}")
        premium = f'<span class="premium-mark"><span aria-hidden="true">✦ </span>{html.escape(f["premium"])}</span>' if f.get("premium") else ""
        items.append(f'<li id="more-{html.escape(f["id"], quote=True)}"><h3>{html.escape(f["title"])}</h3><p>{html.escape(f["text"])}{premium}</p></li>')
    return f'<ul class="more-grid">{"".join(items)}</ul>'


def site_css() -> str:
    """文章のページ（サポート・規約など）の CSS（assets/site.css）"""
    return STYLE.lstrip()


def landing_css(features: list) -> str:
    """紹介ページの CSS（assets/landing.css）。推し色はクラスと CSS の変数で切り替える（style 属性は使わない）"""
    return LANDING_STYLE.lstrip()


def faq_html(questions: list, support_text: str) -> str:
    """サポートの原稿から、挙げた見出しの節（### 見出し 〜 次の見出しまで）を切り出す。見つからなければ止める"""
    out = []
    for i, question in enumerate(questions):
        m = re.search(rf"^### {re.escape(question)}\n(.*?)(?=^#{{2,3}} |\Z)", support_text, flags=re.M | re.S)
        if not m:
            raise BuildError(f"紹介ページ：サポートに「{question}」の質問が見つかりません")
        _, answer = render(m.group(1).strip(), up="")
        opened = " open" if i == 0 else ""
        out.append(f'<details name="faq"{opened}><summary>{html.escape(question)}</summary><div class="answer">{answer}</div></details>')
    return "\n".join(out)


def store_cta(values: dict) -> str:
    """公開前は押せない文字の表示（バッジの形にしない・公開日を書かない）。公開後は App Store のページへのリンク"""
    app_id = str(values.get("app_store_id", "")).strip()
    if not app_id:
        return '<p class="soon"><span aria-hidden="true">✦</span> App Store で近日公開予定</p>'
    url = app_store_url(values, "jp/")
    if not (ASSETS / "app-store-badge.png").exists():
        raise BuildError("Apple 公式の App Store バッジ（src/assets/app-store-badge.png）がありません")
    return f'<a class="store-badge" href="{url}"><img src="assets/app-store-badge.png" width="131" height="48" alt="App Store からダウンロード"></a>'


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
{alternates(values)}
<meta property="og:type" content="website">
<meta property="og:title" content="沼ろく｜推し活の支出記録アプリ">
<meta property="og:description" content="{html.escape(description, quote=True)}">
<meta property="og:url" content="{base}">
<meta property="og:image" content="{base}assets/ogp.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{html.escape(OGP_ALT_JA, quote=True)}">
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
    banner_html = '<div class="draft">下書き：公開前に黄色の箇所を埋めてください</div>' if draft else ""
    return head("沼ろく｜推し活の支出記録アプリ", 0, draft, stylesheet_href("landing.css", landing_css(features)), extra) + f"<body>\n{banner_html}\n{body}\n{footer_html('', values)}\n</body>\n</html>\n"


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
        # 画像の終わり（EOI）の後ろに別の画像（HDR のゲインマップなど。中に Exif を持ちうる）が付いていないこと
        if data.count(b"\xff\xd8\xff") != 1 or not data.rstrip(b"\x00").endswith(b"\xff\xd9"):
            raise BuildError(f"{name}: 画像の後ろに別のデータが付いています")
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


# ---- 検索エンジン向け（sitemap.xml・robots.txt） ----

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NS = "http://www.w3.org/1999/xhtml"


def page_url(base: str, target: str) -> str:
    """出力先（en/support/index.html）→ 公開 URL（…/en/support/）"""
    return base + target.removesuffix("index.html")


def sitemap(outputs: dict, values: dict) -> str:
    """すべてのページの URL。各言語に同じページがあるもの（トップ・サポート・規約・ポリシー）は hreflang で互いを示す。
    x-default は英語（ページの <link rel="alternate"> と同じ考え方）。lastmod は入れない（出力を毎回同じにするため）"""
    base = values["base_url"]
    pages = sorted(name for name in outputs if name.endswith(".html"))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<urlset xmlns="{SITEMAP_NS}" xmlns:xhtml="{XHTML_NS}">']
    for target in pages:
        lines.append(f"<url><loc>{html.escape(page_url(base, target))}</loc>")
        lang_dir = target.split("/")[0]
        rest = target[len(lang_dir) + 1:] if lang_dir in LANG_OF_DIR else target
        group = {"ja": rest} | {code: f"{lang['dir']}/{rest}" for code, lang in LANGS.items()}
        if all(t in outputs for t in group.values()):
            for code, t in group.items():
                lines.append(f'<xhtml:link rel="alternate" hreflang="{code}" href="{html.escape(page_url(base, t))}"/>')
            lines.append(f'<xhtml:link rel="alternate" hreflang="x-default" href="{html.escape(page_url(base, group["en"]))}"/>')
        lines.append("</url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def robots(values: dict, draft: bool) -> str:
    """GitHub Pages のプロジェクトサイト（/numaroku-site/）では、検索エンジンはドメインの一番上の /robots.txt しか読まない。
    ここに置くのは、ホスティングを移したときにそのまま使えるようにするため（サイトマップは Search Console で別に知らせる）"""
    if draft:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nAllow: /\n\nSitemap: {values['base_url']}sitemap.xml\n"


def audit_sitemap(content: str, outputs: dict, values: dict):
    """sitemap.xml の URL がすべて自分のサイトの実在するページで、すべてのページが載っていること"""
    base = values["base_url"]
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise BuildError(f"sitemap.xml: XML として読めません（{error}）")
    listed = set()
    for url in root.findall(f"{{{SITEMAP_NS}}}url"):
        links = [url.findtext(f"{{{SITEMAP_NS}}}loc") or ""]
        links += [link.get("href") or "" for link in url.findall(f"{{{XHTML_NS}}}link")]
        for link in links:
            if not link.startswith(base):
                raise BuildError(f"sitemap.xml: 自分のサイト以外の URL です: {link}")
            target = link[len(base):] + "index.html"
            if not link.endswith("/") or target not in outputs:
                raise BuildError(f"sitemap.xml: ページがありません: {link}")
        listed.add(links[0][len(base):] + "index.html")
    missing = sorted(name for name in outputs if name.endswith(".html") and name not in listed)
    if missing:
        raise BuildError(f"sitemap.xml: 載っていないページがあります: {', '.join(missing)}")


# ---- 出力した HTML の検査 ----

class Audit(HTMLParser):
    """許していない要素・属性・リンク先・コメントを見つけたら止める（Markdown 側の検査をすり抜ける生の HTML のため）"""
    # <style> も止める（CSS は assets/*.css だけ。CSP の style-src 'self' と合わせる）
    FORBIDDEN = {"script", "iframe", "object", "embed", "form", "base", "frame", "frameset", "svg", "style"}

    def __init__(self, page_path: str, files: set[str], values: dict):
        super().__init__(convert_charrefs=True)
        self.page, self.files, self.values = page_path, files, values
        self.csp = None

    def error(self, message: str):
        raise BuildError(f"{self.page}: {message}")

    def handle_comment(self, data):
        self.error("HTML のコメントは公開しません（内部メモが残る原因になるため）")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.FORBIDDEN:
            self.error(f"<{tag}> は使えません")
        if tag == "link" and "stylesheet" in (a.get("rel") or "").lower().split():
            href = a.get("href") or ""
            # 同じサイトの assets/ の、このビルドが作った CSS だけ（https:// で書いた自分のサイトも認めない）
            if not re.match(r"^(\.\./)*assets/(site|landing)\.css\?v=[0-9a-f]{10}$", href):
                self.error(f"許していない CSS です: {href}")
        if tag == "img":
            missing = [k for k in ("width", "height", "alt") if a.get(k) is None]
            if missing:
                self.error(f"<img> に {'・'.join(missing)} がありません（レイアウトのずれと読み上げのため）: {a.get('src')}")
        if tag == "meta" and a.get("http-equiv") is not None:
            if a["http-equiv"] != "Content-Security-Policy":
                self.error(f'http-equiv="{a["http-equiv"]}" は使えません（refresh での移動などを防ぐ）')
            self.csp = a.get("content")
        if a.get("target") == "_blank":
            self.error('target="_blank" は使いません')
        for key, value in attrs:
            value = value or ""
            if key.startswith("on"):
                self.error(f"{key} 属性は使えません")
            if key == "style":
                self.error("style 属性は使えません（CSP で 'unsafe-inline' を許していないため。クラスにする）")
            urls = []
            if key in {"href", "src", "poster", "cite", "background", "action", "formaction", "ping", "data", "manifest"}:
                urls = [value]
            elif key in {"srcset", "imagesrcset"}:
                urls = [part.strip().split()[0] for part in value.split(",") if part.strip()]
            elif key == "content" and (a.get("property") in {"og:url", "og:image"} or a.get("name") in {"twitter:image", "twitter:url"}):
                urls = [value]
            for url in urls:
                self.check_url(url)

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
                # 絶対 URL はサイトの一番上から数える（ページの場所からではない）
                page, self.page = self.page, "index.html"
                try:
                    self.check_url(url[len(self.values["base_url"]):] or "./")
                finally:
                    self.page = page
            if host == "apps.apple.com" and not APP_STORE_URL.match(url):
                self.error(f"App Store の URL の形が正しくありません: {url}")
            return
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
            self.error(f"許していないリンク先です: {url}")
        # 同じサイトの中：ページの場所から実在するファイルを確かめる
        base = self.page.rsplit("/", 1)[0] if "/" in self.page else ""
        path = url.split("#")[0].split("?")[0]
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


def audit(outputs: dict[str, bytes | str], values: dict, draft: bool = False):
    files = set(outputs)
    for name, content in outputs.items():
        suffix = Path(name).suffix
        if suffix not in ALLOWED_SUFFIXES:
            raise BuildError(f"{name}: 置けない種類のファイルです")
        if suffix in {".css", ".xml", ".txt"} and name not in GENERATED_TEXT_FILES:
            raise BuildError(f"{name}: このビルドが作る決まったファイル以外の .css・.xml・.txt は置けません")
        if suffix == ".css":
            m = CSS_FORBIDDEN.search(content)
            if m:
                raise BuildError(f"{name}: CSS に使えないもの（{m.group(0)}）があります（外部の読み込み・エスケープは使わない）")
            if UNRESOLVED.search(content):
                raise BuildError(f"{name}: 【】・TODO・要確認 が残っています")
        if name == "sitemap.xml":
            audit_sitemap(content, outputs, values)
        if name == "robots.txt" and content != robots(values, draft):
            raise BuildError("robots.txt: 決まった中身と違います")
        if suffix != ".html":
            continue
        checker = Audit(name, files, values)
        checker.feed(content)
        checker.close()
        if checker.csp != CSP:
            raise BuildError(f"{name}: CSP が決まったものと違います")
        if UNRESOLVED.search(re.sub(r"<[^>]+>", "", content)):
            raise BuildError(f"{name}: 【】・TODO・要確認 が残っています")
        for claim in STALE_CLAIMS:
            if claim in content:
                raise BuildError(f"{name}: 実装と食い違う古い表記「{claim}」が残っています")
    landing_page = outputs["index.html"]
    # 1.0 のアプリはトップをサポートとして開くので、トップからサポートと問い合わせ先にすぐ行けること
    if 'href="support/"' not in landing_page or f'href="mailto:{values["contact"]}"' not in landing_page:
        raise BuildError("index.html: トップにサポートへのリンクと問い合わせ先がありません")
    # 1.3 のアプリは日本語以外の言語で /<dir>/ をサポートとして開くので、各言語のトップも同じにする
    for lang in LANGS.values():
        top = outputs[f"{lang['dir']}/index.html"]
        if f'href="../{lang["dir"]}/support/"' not in top or f'href="mailto:{values["contact"]}"' not in top:
            raise BuildError(f"{lang['dir']}/index.html: トップにサポートへのリンクと問い合わせ先がありません")


def main() -> int:
    release = "--release" in sys.argv[1:]
    dist = ROOT / ("docs" if release else "draft")
    values = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    outputs: dict[str, bytes | str] = {}
    problems = []
    try:
        support_text = ""
        tokushoho_text = ""
        for target, source, fallback in PAGES + PAGES_INTL:
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
            lang = LANG_OF_DIR.get(target.split("/")[0], "ja")
            if lang != "ja":
                # 見出しの語順は言語ごとに違うので、ページの題名は決まった名前にする（トップは Numaroku）
                title = fallback
            else:
                title = title.removeprefix("沼ろく ").strip() or fallback
            outputs[target] = page(title, body, depth, draft=bool(left), values=values, lang=lang)
        check_prices(values, tokushoho_text)
        outputs["index.html"] = landing(values, support_text, draft=bool(problems))
        features = json.loads((ROOT / "src" / "landing_features.json").read_text(encoding="utf-8"))
        outputs["assets/site.css"] = site_css()
        outputs["assets/landing.css"] = landing_css(features)
        outputs.update(assets())
        outputs["sitemap.xml"] = sitemap(outputs, values)
        outputs["robots.txt"] = robots(values, draft=not release)
        audit(outputs, values, draft=not release)
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
        odd = sorted(name for name in outputs if Path(name).suffix not in ALLOWED_SUFFIXES
                     or (Path(name).suffix in {".css", ".xml", ".txt"} and name not in GENERATED_TEXT_FILES))
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
