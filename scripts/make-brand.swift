// Regenerates the brand images: the app icon (a flat split baked russet with a butter pat on Sawtooth-pine green; Nick's pick
// 2026-10-08, concept A of scripts/icon-concepts.swift, redrawn 2026-10-09 in the shared Eats Ranked icon style Nick approved, same
// food and colours with no ridge, snow, chives, puddle or tilt: ../state-prompts/ICON-STYLE.md), playbook/brand/, and the site's
// og.png, favicons and manifest icons. Flat and matte (Nick's rule from Colorado and Washington: no gloss).
// Usage: swift scripts/make-brand.swift [count]   (run from id-eats/)
import AppKit
import CoreGraphics

let root = FileManager.default.currentDirectoryPath
func rgb(_ hex: UInt32, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((hex >> 16) & 255) / 255, green: CGFloat((hex >> 8) & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: a)
}
let pine = rgb(0x2E5A4C), huck = rgb(0x4B2A5C), cream = rgb(0xF8F4EC), russet = rgb(0xC9A06B)

func canvas(_ w: Int, _ h: Int, _ draw: (CGContext) -> Void) -> CGImage {
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    ctx.setShouldAntialias(true); ctx.interpolationQuality = .high
    draw(ctx)
    return ctx.makeImage()!
}
func save(_ img: CGImage, _ path: String) {
    let url = URL(fileURLWithPath: root + "/" + path)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    try! NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:])!.write(to: url)
    print("wrote", path)
}
func P(_ s: CGFloat, _ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * s, y: y * s) }
func dot(_ c: CGContext, _ s: CGFloat, _ x: CGFloat, _ y: CGFloat, _ r: CGFloat) {
    c.fillEllipse(in: CGRect(x: s * (x - r), y: s * (y - r), width: s * r * 2, height: s * r * 2))
}

/// The food alone (no ground): a split baked russet lying flat (side view), skin with a flat underside, 3 eyes, the cream split
/// and a butter pat square to the canvas. Eats Ranked icon style v1 (2026-10-09). Geometry is in fractions of the canvas with y
/// measured from the TOP, like the style guide; `T` flips it for CoreGraphics.
func potatoFood(_ c: CGContext, _ s: CGFloat) {
    func T(_ x: CGFloat, _ y: CGFloat) -> CGPoint { P(s, x, 1 - y) }
    let skin = rgb(0xA8713E), under = rgb(0x8A5A30), flesh = rgb(0xF6E7B6), butter = rgb(0xE9B832)   // 5 colours with the pine
    let px1: CGFloat = 1 / 1024                                    // one pixel at 1024
    let cx: CGFloat = 0.5, cy: CGFloat = 0.519, rx: CGFloat = 0.36, ry: CGFloat = 0.21   // potato ellipse 0.72 x 0.42, 20 px low
    let skinTop = cy - ry                                          // 0.309, the potato's highest point
    let shadeEdge = cy + ry - 2 * ry * 0.28                        // underside: the lower 28% of the potato, hard horizontal edge

    // Skin: a plain ellipse; the clip only keeps each flat tone inside it.
    let body = CGPath(ellipseIn: CGRect(x: (cx - rx) * s, y: (1 - cy - ry) * s, width: 2 * rx * s, height: 2 * ry * s), transform: nil)
    c.saveGState(); c.addPath(body); c.clip()
    c.setFillColor(skin); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    c.setFillColor(under); c.fill(CGRect(x: 0, y: 0, width: s, height: (1 - shadeEdge) * s))
    c.restoreGState()

    // Eyes: 3 horizontal ovals 50 x 34 px in the underside's tone, on bare skin clear of the split (two on the upper shoulders,
    // one low on the right, its bottom 30 px above the underside edge).
    let eyeW = 50 * px1, eyeH = 34 * px1
    c.setFillColor(under)
    for (x, y) in [(0.25, 0.492), (0.75, 0.482), (0.58, shadeEdge - 30 * px1 - eyeH / 2)] as [(CGFloat, CGFloat)] {
        c.fillEllipse(in: CGRect(x: (x - eyeW / 2) * s, y: (1 - y - eyeH / 2) * s, width: eyeW * s, height: eyeH * s))
    }

    // The split: a cream lens 0.48 wide, 0.145 tall at the middle, its top 36 px under the skin top (the far lip). Its ends sit
    // where 60 px of skin remains to the potato's side. A cubic reaches 3/4 of its handles' offset at the middle, hence the /0.75.
    let lensHalf: CGFloat = 0.24, lensTop = skinTop + 0.035, lensBottom = lensTop + 0.145
    let hw = lensHalf + 60 * px1
    let tip = cy - ry * (1 - (hw / rx) * (hw / rx)).squareRoot()
    let x0 = cx - lensHalf, x1 = cx + lensHalf
    let kTop = tip + (lensTop - tip) / 0.75, kBot = tip + (lensBottom - tip) / 0.75
    let lens = CGMutablePath()
    lens.move(to: T(x0, tip))
    lens.addCurve(to: T(x1, tip), control1: T(x0 + 0.09, kTop), control2: T(x1 - 0.09, kTop))
    lens.addCurve(to: T(x0, tip), control1: T(x1 - 0.115, kBot), control2: T(x0 + 0.115, kBot))
    lens.closeSubpath()
    c.setFillColor(flesh); c.addPath(lens); c.fillPath()

    // The butter pat: flat, 0.18 wide, radius 12 px, top 10 px above the skin top, bottom 60 px into the cream.
    let patW: CGFloat = 0.18, patTopY = skinTop - 10 * px1, patBottomY = lensTop + 60 * px1
    let pat = CGRect(x: (cx - patW / 2) * s, y: (1 - patBottomY) * s, width: patW * s, height: (patBottomY - patTopY) * s)
    let r = s * 12 / 1024
    c.setFillColor(butter); c.addPath(CGPath(roundedRect: pat, cornerWidth: r, cornerHeight: r, transform: nil)); c.fillPath()
}

/// The app icon: one flat Sawtooth-pine ground, edge to edge, then the food. og.png draws it whole in a rounded tile (icon(380)).
func potato(_ c: CGContext, _ s: CGFloat) {
    c.setFillColor(pine); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    potatoFood(c, s)
}

func icon(_ size: Int) -> CGImage {
    canvas(size, size) { c in potato(c, CGFloat(size)) }
}

func text(_ c: CGContext, _ str: String, font: NSFont, color: CGColor, at p: CGPoint) {
    let attr = NSAttributedString(string: str, attributes: [.font: font, .foregroundColor: NSColor(cgColor: color)!])
    c.textPosition = p
    CTLineDraw(CTLineCreateWithAttributedString(attr), c)
}
func heavy(_ size: CGFloat) -> NSFont {
    NSFont(name: "HelveticaNeue-CondensedBlack", size: size) ?? NSFont.systemFont(ofSize: size, weight: .black)
}

let appIcon = icon(1024)
save(appIcon, "IdahoEats/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png")
save(appIcon, "playbook/brand/icon-1024.png")
save(icon(512), "docs/icon-512.png")
save(icon(192), "docs/icon-192.png")
save(icon(180), "docs/apple-touch-icon.png")
save(icon(32), "docs/favicon-32.png")

let count = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "4,000+"
let og = canvas(1200, 630) { c in
    c.setFillColor(huck); c.fill(CGRect(x: 0, y: 0, width: 1200, height: 630))
    c.setFillColor(russet); c.fill(CGRect(x: 72, y: 470, width: 90, height: 12))
    text(c, "IDAHO", font: heavy(128), color: cream, at: CGPoint(x: 66, y: 322))
    text(c, "EATS", font: heavy(128), color: russet, at: CGPoint(x: 66, y: 204))
    // three short lines, all left of the icon (one long line ran under it and was cut off)
    text(c, "Finger steaks, Basque & spud guide", font: NSFont.systemFont(ofSize: 32, weight: .semibold), color: cream, at: CGPoint(x: 70, y: 150))
    text(c, "\(count) Idaho restaurants", font: NSFont.systemFont(ofSize: 30, weight: .regular), color: cream, at: CGPoint(x: 70, y: 104))
    text(c, "Free for iPhone and iPad", font: NSFont.systemFont(ofSize: 30, weight: .regular), color: russet, at: CGPoint(x: 70, y: 58))
    // the icon itself, rounded, on the right
    let mask = CGPath(roundedRect: CGRect(x: 760, y: 130, width: 380, height: 380), cornerWidth: 86, cornerHeight: 86, transform: nil)
    c.saveGState(); c.addPath(mask); c.clip(); c.draw(icon(380), in: CGRect(x: 760, y: 130, width: 380, height: 380)); c.restoreGState()
    c.setFillColor(pine); c.fill(CGRect(x: 0, y: 0, width: 1200, height: 10))
}
save(og, "docs/og.png")
