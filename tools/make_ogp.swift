// SNS で共有されたときの画像（1200×630・OGP）を作る。紺のグラデーション＋アイコン＋見出し＋アプリの画面1枚。
// 使い方: swift tools/make_ogp.swift <アイコン> <画面> <出力 PNG>（tools/make_images.sh から呼ぶ）
import AppKit
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let arguments = CommandLine.arguments
guard arguments.count == 4,
      let iconSource = CGImageSourceCreateWithURL(URL(fileURLWithPath: arguments[1]) as CFURL, nil),
      let icon = CGImageSourceCreateImageAtIndex(iconSource, 0, nil),
      let shotSource = CGImageSourceCreateWithURL(URL(fileURLWithPath: arguments[2]) as CFURL, nil),
      let shot = CGImageSourceCreateImageAtIndex(shotSource, 0, nil) else {
    let usage = "使い方: swift tools/make_ogp.swift <アイコン> <画面> <出力 PNG>\n"
    FileHandle.standardError.write(Data(usage.utf8))
    exit(1)
}

func color(_ hex: UInt32, _ alpha: CGFloat = 1) -> CGColor {
    CGColor(red: CGFloat(hex >> 16 & 0xFF) / 255, green: CGFloat(hex >> 8 & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255, alpha: alpha)
}

let size = CGSize(width: 1200, height: 630)
guard let space = CGColorSpace(name: CGColorSpace.sRGB),
      let context = CGContext(data: nil, width: 1200, height: 630, bitsPerComponent: 8, bytesPerRow: 0,
                              space: space, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue),
      let gradient = CGGradient(colorsSpace: space, colors: [color(0x2A1F4F), color(0x121628)] as CFArray,
                                locations: [0, 1])
else { exit(1) }
context.drawLinearGradient(gradient, start: CGPoint(x: 0, y: size.height), end: CGPoint(x: size.width, y: 0),
                           options: [])
// ペンライト色の光
for (hex, ratio) in [(UInt32(0xFF6FA3), CGPoint(x: 0.15, y: 0.85)), (0x4A90E2, CGPoint(x: 0.9, y: 0.2)),
                     (0xA066E8, CGPoint(x: 0.6, y: 0.95))] {
    let center = CGPoint(x: size.width * ratio.x, y: size.height * ratio.y)
    let colors = [color(hex, 0.35), color(hex, 0)] as CFArray
    if let glow = CGGradient(colorsSpace: space, colors: colors, locations: [0, 1]) {
        context.drawRadialGradient(glow, startCenter: center, startRadius: 0, endCenter: center, endRadius: 360,
                                   options: [])
    }
}

// アイコン（角丸）
let iconRect = CGRect(x: 80, y: 630 - 80 - 120, width: 120, height: 120)
context.saveGState()
context.addPath(CGPath(roundedRect: iconRect, cornerWidth: 27, cornerHeight: 27, transform: nil))
context.clip()
context.draw(icon, in: iconRect)
context.restoreGState()

// 文字
func draw(_ string: String, _ rect: CGRect, size fontSize: CGFloat, weight: String, alpha: CGFloat = 1) {
    let font = NSFont(name: weight, size: fontSize) ?? NSFont.boldSystemFont(ofSize: fontSize)
    let paragraph = NSMutableParagraphStyle()
    paragraph.lineSpacing = fontSize * 0.25
    let text = NSAttributedString(string: string, attributes: [
        .font: font, .foregroundColor: NSColor.white.withAlphaComponent(alpha), .paragraphStyle: paragraph
    ])
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(cgContext: context, flipped: false)
    text.draw(in: rect)
    NSGraphicsContext.restoreGraphicsState()
}
draw("沼ろく", CGRect(x: 222, y: 438, width: 500, height: 80), size: 52, weight: "HiraginoSans-W7")
draw("推しに使ったお金、\nぜんぶ思い出に。", CGRect(x: 80, y: 200, width: 700, height: 220), size: 64, weight: "HiraginoSans-W7")
draw("推し活の支出記録アプリ｜iPhone", CGRect(x: 80, y: 110, width: 700, height: 50), size: 30,
     weight: "HiraginoSans-W4", alpha: 0.8)

// 画面（角丸・少し下にはみ出す）
let shotWidth: CGFloat = 300
let shotHeight = shotWidth * CGFloat(shot.height) / CGFloat(shot.width)
let shotRect = CGRect(x: 820, y: 630 - 60 - shotHeight, width: shotWidth, height: shotHeight)
let path = CGPath(roundedRect: shotRect, cornerWidth: 40, cornerHeight: 40, transform: nil)
context.saveGState()
context.setShadow(offset: .zero, blur: 40, color: color(0xFF6FA3, 0.5))
context.addPath(path)
context.setFillColor(color(0x121628))
context.fillPath()
context.restoreGState()
context.saveGState()
context.addPath(path)
context.clip()
context.draw(shot, in: shotRect)
context.restoreGState()

guard let image = context.makeImage(),
      let destination = CGImageDestinationCreateWithURL(URL(fileURLWithPath: arguments[3]) as CFURL,
                                                        UTType.png.identifier as CFString, 1, nil)
else { exit(1) }
CGImageDestinationAddImage(destination, image, [kCGImageMetadataShouldExcludeGPS: true] as CFDictionary)
CGImageDestinationFinalize(destination)
