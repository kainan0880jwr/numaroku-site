#!/bin/bash
# 紹介ページの画像を作る（macOS 標準の sips と swift だけ。外部のパッケージは使わない）。
# 使い方: tools/make_images.sh   → src/assets/ に作る（公開してよい画像だけを置く場所。build.py がメタデータを消して docs/assets/ へ写す）
#
# 元の画像（アプリのリポジトリ oshikatsu）:
#   アイコン      … App/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png
#   画面          … screenshots/iPhone 17 Pro/（2026-10-12 に 1.0 で撮った、見出しなしの画面。架空のデータだけ）
# ★ 1.1 の画面（イベント・ロック画面など）を使わないこと。1.1 の紹介は 1.1 の公開と同時に release-1.1 ブランチで足す
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/../oshikatsu"
ICON="$APP/App/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"
SHOTS="$APP/screenshots/iPhone 17 Pro"
OUT="$ROOT/src/assets"
SRGB="/System/Library/ColorSync/Profiles/sRGB Profile.icc"
mkdir -p "$OUT"

# アイコン（PNG）
for size in 32 180 192 512; do
  sips -s format png --matchTo "$SRGB" -z "$size" "$size" "$ICON" --out "$OUT/icon-$size.png" >/dev/null
done

# 画面（JPEG・sRGB・幅 320/640）。紹介ページで使う4枚だけ
for name in 1_entry 2_home 3_summary 4_monthly_recap; do
  out="${name#*_}"; out="${out//_/-}"   # 4_monthly_recap → monthly-recap
  for width in 320 640; do
    sips -s format jpeg -s formatOptions 80 --matchTo "$SRGB" --resampleWidth "$width" \
      "$SHOTS/$name.png" --out "$OUT/screen-$out-$width.jpg" >/dev/null
  done
done

# SNS で共有されたときの画像（1200×630）
swift "$ROOT/tools/make_ogp.swift" "$ICON" "$SHOTS/2_home.png" "$OUT/ogp.png"
sips -s format jpeg -s formatOptions 82 "$OUT/ogp.png" --out "$OUT/ogp.jpg" >/dev/null
rm "$OUT/ogp.png"

ls -la "$OUT"
