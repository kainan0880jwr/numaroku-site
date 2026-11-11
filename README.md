# numaroku-site

iPhone アプリ「沼ろく」の紹介ページと、サポート・利用規約・プライバシーポリシー・特定商取引法に基づく表記のページです。
静的な HTML だけで、JavaScript・外部の読み込み・解析ツール・Cookie は使っていません。

公開 URL：https://kainan0880jwr.github.io/numaroku-site/

| ページ | 場所 | 原稿 |
|---|---|---|
| 紹介ページ | `/` | `src/landing.html`（本文）・`src/landing.css`（見た目）・`src/landing_features.json`（「ほかにも」の格子）・`site.json`（料金・問い合わせ先・よくある質問の見出し） |
| サポート | `/support/` | `src/support.md` |
| 利用規約・プライバシーポリシー | `/terms/`・`/privacy/` | `../../oshikatsu/legal/` |
| 特定商取引法に基づく表記 | `/tokushoho/` | `src/tokushoho.md` |

| 作業 | コマンド |
|---|---|
| 下書きを作る（`draft/`。未記入の箇所を黄色で表示・検索エンジンに載せない） | `python3 -I tools/build.py` |
| 公開用を作る（`docs/`。未記入・内部メモ・許可していないリンクが1つでもあれば作らずに止まる） | `python3 -I tools/build.py --release` |
| 手元で見る | `cd draft && python3 -I -m http.server 8765 --bind 127.0.0.1` |
| 紹介ページの画像を作り直す（`src/assets/`） | `tools/make_images.sh` |

- 公開するのは `docs/`（GitHub Pages の公開元：main ブランチの /docs）。`draft/` は Git に入れない
- 運営者名・問い合わせ先・制定日・著作権表示は `site.json` に書く
- 原稿を直したら `--release` で作り直し、`docs/` の差分を確かめてからコミットする

## 守ること
- **トップ `/` には、サポートへのリンクと問い合わせ先を常に置く**。1.0・1.1 のアプリと App Store Connect のサポート URL がトップを開くため（`build.py` の検査でも確かめる）
- `/terms/`・`/privacy/`・`/tokushoho/` のパスは変えない（アプリが固定で持っている）。GitHub のユーザー名・このリポジトリの名前を変えない・消さない・非公開にしない・Pages を止めない
- 紹介ページに載せるのは、App Store で公開済みのバージョンの機能だけ。画像も公開済みのバージョンで撮った画面だけ（`tools/make_images.sh` の元の画像）
- 料金・無料体験は `site.json` と `src/tokushoho.md` を同じ日に直す（違えば `--release` が止まる）。App Store Connect で価格やオファーを変えたら、サイトも同じ日に直す
- CSP・外部リンクの許可先・ファイルの種類は `build.py` の定数で決めている。`--release` は、出力したすべての HTML を読み直して、`<script>`・HTML のコメント・許していないリンク先・無いファイルへのリンク・画像のメタデータがあれば止まる
- CSS は `build.py` の `STYLE`（文章のページ → `assets/site.css`）と `src/landing.css`（紹介ページ → `assets/landing.css`。2026-11 の作り直しで外に出した）に書き、同一オリジンのファイルとして出す。CSP は `style-src 'self'`（`'unsafe-inline'` なし）なので、`<style>` と `style` 属性は使えない（検査で止まる）。CSS に `url(`・`@import`・`\` があっても止まる
- `sitemap.xml`（hreflang 付き。x-default は英語）と `robots.txt` も作る。ただし GitHub Pages のプロジェクトサイトでは、検索エンジンはドメインの一番上の `/robots.txt` しか読まないので、サイトマップを知らせるには Search Console に登録する（運営者が行う）
- 紹介ページの主役の機能（記録・推し活ならでは・ふり返り・イベント・安心・料金）は `src/landing.html` に直接書く。細かい機能は `src/landing_features.json` の「ほかにも」の格子（`premium` に書いた文は ✦ の印付きで出る）
- 紹介ページの動き（scroll-driven animations・view transitions・FAQ の開閉）は、すべて `prefers-reduced-motion: no-preference` と `@supports` の中。動かない環境でも内容は最初から見えている。「推し色を選んでみて」は `:has()` とラジオボタンで、JS は使わない
- **1.10 のポリシー改定（2026-11-11）**：ポリシーの原稿に【要記入：1.10 の公開日】（翻訳版は（en）など）がある。1.10 が App Store で公開された日に、`site.json` に `revised_1_10`（日本語の日付）と `revised_1_10_<言語>`（en・de・es・fr・hi・id・it・pt-BR・tr・vi。各言語の日付の書き方）を書く。書くまではどのブランチでもビルドが止まる（公開前のポリシーを出さないため）
- `docs/` に今回作っていないファイルが残っていると止まる。消すのは確かめてから人が行う

