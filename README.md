# numaroku-site

iPhone アプリ「沼ろく」のサポート・利用規約・プライバシーポリシー・特定商取引法に基づく表記のページです。
静的な HTML だけで、外部のスクリプト・解析ツール・Cookie は使っていません。

公開 URL：https://kainan0880jwr.github.io/numaroku-site/

| 作業 | コマンド |
|---|---|
| 下書きを作る（`draft/`。未記入の箇所を黄色で表示・検索エンジンに載せない） | `python3 -I tools/build.py` |
| 公開用を作る（`docs/`。未記入・内部メモ・許可していないリンクが1つでもあれば作らずに止まる） | `python3 -I tools/build.py --release` |
| 手元で見る | `cd draft && python3 -I -m http.server 8765 --bind 127.0.0.1` |

- 公開するのは `docs/`（GitHub Pages の公開元：main ブランチの /docs）。`draft/` は Git に入れない
- 運営者名・問い合わせ先・制定日・著作権表示は `site.json` に書く
- 原稿を直したら `--release` で作り直し、`docs/` の差分を確かめてからコミットする
