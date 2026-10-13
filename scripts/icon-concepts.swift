// Idaho icon concepts (2026-10-08), flat and matte (Nick's rule from Colorado and Washington: no gloss).
// A: split baked russet with a butter pat · B: huckleberry cluster with a leaf · C: finger steaks with a fry-sauce cup.
// Each sits on a landscape ground with a jagged Sawtooth ridge along the bottom.
// Usage: swift scripts/icon-concepts.swift   (run from id-eats/) -> playbook/brand/concepts.png and concept-<x>-1024.png
import AppKit
import CoreGraphics

let root = FileManager.default.currentDirectoryPath
func rgb(_ hex: UInt32, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((hex >> 16) & 255) / 255, green: CGFloat((hex >> 8) & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: a)
}
let pine = rgb(0x2E5A4C), pine2 = rgb(0x24493D), huck = rgb(0x4B2A5C), huck2 = rgb(0x3B2148), cream = rgb(0xF8F4EC)
let white = rgb(0xFFFFFF), ink = rgb(0x1F1A24)

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

/// The Sawtooth ridge: sharp, uneven granite teeth along the bottom of the icon.
func ridge(_ c: CGContext, _ s: CGFloat, _ color: CGColor, snow: CGColor?) {
    let pts: [(CGFloat, CGFloat)] = [(0, 0.12), (0.07, 0.17), (0.11, 0.14), (0.17, 0.23), (0.21, 0.17), (0.27, 0.26), (0.31, 0.19),
                                     (0.36, 0.21), (0.42, 0.30), (0.47, 0.21), (0.52, 0.25), (0.58, 0.18), (0.64, 0.27), (0.69, 0.20),
                                     (0.75, 0.24), (0.81, 0.16), (0.87, 0.21), (0.93, 0.15), (1, 0.18)]
    let r = CGMutablePath()
    r.move(to: P(s, 0, 0)); for (x, y) in pts { r.addLine(to: P(s, x, y)) }; r.addLine(to: P(s, 1, 0)); r.closeSubpath()
    c.setFillColor(color); c.addPath(r); c.fillPath()
    guard let snow else { return }
    c.saveGState(); c.addPath(r); c.clip(); defer { c.restoreGState() }   // snow stays inside the ridge's outline
    c.setFillColor(snow)
    for (x, y) in [(0.42, 0.30), (0.27, 0.26), (0.64, 0.27)] as [(CGFloat, CGFloat)] {
        let cap = CGMutablePath()
        cap.move(to: P(s, x, y + 0.01)); cap.addLine(to: P(s, x - 0.06, y - 0.045)); cap.addLine(to: P(s, x - 0.015, y - 0.035))
        cap.addLine(to: P(s, x + 0.008, y - 0.05)); cap.addLine(to: P(s, x + 0.06, y - 0.04)); cap.closeSubpath()
        c.addPath(cap); c.fillPath()
    }
}

/// A: a russet baked potato, split along the top, with a butter pat melting in the split. Pine-green ground.
func potato(_ c: CGContext, _ s: CGFloat) {
    c.setFillColor(pine); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    ridge(c, s, pine2, snow: rgb(0xFFFFFF, 0.75))
    // the potato: a long russet oval, skin in two flat browns
    let body = CGPath(ellipseIn: CGRect(x: s * 0.11, y: s * 0.27, width: s * 0.78, height: s * 0.46), transform: nil)
    c.saveGState(); c.addPath(body); c.clip()
    c.setFillColor(rgb(0xA8713E)); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    c.setFillColor(rgb(0x8A5A30)); c.fill(CGRect(x: 0, y: 0, width: s, height: s * 0.40))   // the shaded underside, flat
    c.setFillColor(rgb(0x6E4523))
    for (x, y, r) in [(0.22, 0.43, 0.012), (0.30, 0.35, 0.010), (0.70, 0.36, 0.012), (0.80, 0.47, 0.010), (0.58, 0.31, 0.009),
                      (0.42, 0.32, 0.010)] as [(CGFloat, CGFloat, CGFloat)] { dot(c, s, x, y, r) }
    c.restoreGState()
    // the split: a fluffy cream opening across the top
    let split = CGMutablePath()
    split.move(to: P(s, 0.20, 0.56))
    split.addCurve(to: P(s, 0.80, 0.56), control1: P(s, 0.36, 0.72), control2: P(s, 0.64, 0.72))
    split.addCurve(to: P(s, 0.20, 0.56), control1: P(s, 0.64, 0.47), control2: P(s, 0.36, 0.47))
    split.closeSubpath()
    c.setFillColor(rgb(0xF6E7B6)); c.addPath(split); c.fillPath()
    // the butter pat: a square, a little tilted, with a lighter top face and a melted puddle
    c.setFillColor(rgb(0xF7D35A)); c.fillEllipse(in: CGRect(x: s * 0.36, y: s * 0.54, width: s * 0.28, height: s * 0.09))
    c.saveGState()
    c.translateBy(x: s * 0.50, y: s * 0.635); c.rotate(by: -0.18)
    let pat = CGRect(x: -s * 0.085, y: -s * 0.055, width: s * 0.17, height: s * 0.11)
    c.setFillColor(rgb(0xE9B832)); c.addPath(CGPath(roundedRect: pat, cornerWidth: s * 0.012, cornerHeight: s * 0.012, transform: nil)); c.fillPath()
    c.setFillColor(rgb(0xFFE07A))
    c.addPath(CGPath(roundedRect: CGRect(x: pat.minX, y: pat.midY - s * 0.005, width: pat.width, height: pat.height / 2 + s * 0.005),
                     cornerWidth: s * 0.012, cornerHeight: s * 0.012, transform: nil)); c.fillPath()
    c.restoreGState()
    // a few chives
    c.setFillColor(rgb(0x5F9E3C))
    for (x, y) in [(0.31, 0.59), (0.69, 0.60), (0.40, 0.66), (0.62, 0.67)] as [(CGFloat, CGFloat)] { dot(c, s, x, y, 0.012) }
}

/// B: a huckleberry cluster on a sprig, with one leaf. Cream ground, pine ridge.
func huckleberries(_ c: CGContext, _ s: CGFloat) {
    c.setFillColor(cream); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    ridge(c, s, pine, snow: nil)
    // the sprig and leaf
    let twig = CGMutablePath()
    twig.move(to: P(s, 0.70, 0.88)); twig.addCurve(to: P(s, 0.50, 0.62), control1: P(s, 0.66, 0.78), control2: P(s, 0.57, 0.68))
    c.setStrokeColor(rgb(0x6B4A2B)); c.setLineWidth(s * 0.025); c.setLineCap(.round); c.addPath(twig); c.strokePath()
    let leaf = CGMutablePath()
    leaf.move(to: P(s, 0.66, 0.78))
    leaf.addCurve(to: P(s, 0.92, 0.84), control1: P(s, 0.74, 0.92), control2: P(s, 0.86, 0.94))
    leaf.addCurve(to: P(s, 0.66, 0.78), control1: P(s, 0.88, 0.72), control2: P(s, 0.74, 0.70))
    c.setFillColor(rgb(0x4F8A3A)); c.addPath(leaf); c.fillPath()
    let rib = CGMutablePath(); rib.move(to: P(s, 0.68, 0.78)); rib.addCurve(to: P(s, 0.90, 0.835), control1: P(s, 0.76, 0.81), control2: P(s, 0.84, 0.83))
    c.setStrokeColor(rgb(0x3A6B2A)); c.setLineWidth(s * 0.012); c.addPath(rib); c.strokePath()
    // berries: deep purple-blue, a flat lighter crescent on each (matte), and the five-point crown at the bottom of the berry
    let berries: [(CGFloat, CGFloat, CGFloat)] = [(0.35, 0.55, 0.17), (0.63, 0.48, 0.16), (0.48, 0.32, 0.15), (0.21, 0.34, 0.125)]
    for (x, y, r) in berries {
        c.setFillColor(rgb(0x3F2E6E)); dot(c, s, x, y, r)
        c.saveGState()
        c.addEllipse(in: CGRect(x: s * (x - r), y: s * (y - r), width: s * r * 2, height: s * r * 2)); c.clip()
        c.setFillColor(rgb(0x5B4A8E)); dot(c, s, x - r * 0.28, y + r * 0.30, r * 0.78)
        c.setFillColor(rgb(0x3F2E6E)); dot(c, s, x - r * 0.05, y + r * 0.02, r * 0.82)
        c.restoreGState()
        c.setFillColor(rgb(0x2A1D4C)); dot(c, s, x + r * 0.30, y - r * 0.32, r * 0.22)
        c.setFillColor(rgb(0x5B4A8E)); dot(c, s, x + r * 0.30, y - r * 0.32, r * 0.09)
    }
}

/// C: finger steaks (battered strips) fanned in a paper boat, with a cup of fry sauce. Huckleberry ground.
func fingerSteaks(_ c: CGContext, _ s: CGFloat) {
    c.setFillColor(huck); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    ridge(c, s, huck2, snow: rgb(0xFFFFFF, 0.7))
    // the strips: golden, knobbly, leaning out of the boat
    let strips: [(CGFloat, CGFloat, CGFloat)] = [(0.24, 0.42, 0.42), (0.36, 0.46, 0.20), (0.48, 0.47, -0.02), (0.60, 0.45, -0.24)]
    for (x, y, a) in strips {
        c.saveGState(); c.translateBy(x: s * x, y: s * y); c.rotate(by: a)
        let r = CGRect(x: -s * 0.055, y: 0, width: s * 0.11, height: s * 0.38)
        c.setFillColor(rgb(0xC98A35)); c.addPath(CGPath(roundedRect: r, cornerWidth: s * 0.05, cornerHeight: s * 0.05, transform: nil)); c.fillPath()
        c.setFillColor(rgb(0xE6B05A))
        c.addPath(CGPath(roundedRect: r.insetBy(dx: s * 0.018, dy: s * 0.02), cornerWidth: s * 0.035, cornerHeight: s * 0.035, transform: nil)); c.fillPath()
        c.setFillColor(rgb(0xC98A35))
        for yy in [0.12, 0.22, 0.30] as [CGFloat] { dot(c, s, 0.012, yy, 0.012); dot(c, s, -0.015, yy + 0.05, 0.010) }
        c.restoreGState()
    }
    // the paper boat: red and white check
    let boat = CGMutablePath()
    boat.move(to: P(s, 0.14, 0.50)); boat.addLine(to: P(s, 0.70, 0.50)); boat.addLine(to: P(s, 0.63, 0.27)); boat.addLine(to: P(s, 0.21, 0.27)); boat.closeSubpath()
    c.saveGState(); c.addPath(boat); c.clip()
    c.setFillColor(white); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    c.setFillColor(rgb(0xC8323A))
    let cell = s * 0.06
    for i in 0..<18 { for j in 0..<18 where (i + j) % 2 == 0 {
        c.fill(CGRect(x: CGFloat(i) * cell, y: s * 0.27 + CGFloat(j) * cell, width: cell, height: cell))
    } }
    c.restoreGState()
    // the fry-sauce cup: a white cup with the pink-orange sauce
    c.setFillColor(white)
    let cup = CGMutablePath()
    cup.move(to: P(s, 0.66, 0.44)); cup.addLine(to: P(s, 0.90, 0.44)); cup.addLine(to: P(s, 0.87, 0.28)); cup.addLine(to: P(s, 0.69, 0.28)); cup.closeSubpath()
    c.addPath(cup); c.fillPath()
    c.setFillColor(rgb(0xE9DFF0)); c.fill(CGRect(x: s * 0.69, y: s * 0.28, width: s * 0.18, height: s * 0.03))
    c.setFillColor(rgb(0xF2946B)); c.fillEllipse(in: CGRect(x: s * 0.66, y: s * 0.405, width: s * 0.24, height: s * 0.07))
    c.setFillColor(rgb(0xF7B08E)); c.fillEllipse(in: CGRect(x: s * 0.70, y: s * 0.43, width: s * 0.09, height: s * 0.025))
}

let concepts: [(String, String, (CGContext, CGFloat) -> Void)] = [
    ("a", "A · Split baked russet", potato), ("b", "B · Huckleberries", huckleberries), ("c", "C · Finger steaks + fry sauce", fingerSteaks)]
func icon(_ size: Int, _ f: (CGContext, CGFloat) -> Void) -> CGImage {
    canvas(size, size) { c in f(c, CGFloat(size)) }
}
let sheet = canvas(1060, 3 * 600 + 40) { c in
    c.setFillColor(white); c.fill(CGRect(x: 0, y: 0, width: 1060, height: 3 * 600 + 40))
    for (i, (_, label, f)) in concepts.enumerated() {
        let y0 = CGFloat(3 * 600 + 40 - (i + 1) * 600)
        let mask = CGPath(roundedRect: CGRect(x: 0, y: 0, width: 1, height: 1), cornerWidth: 0.225, cornerHeight: 0.225, transform: nil)
        for (sz, x) in [(512, 40), (180, 600), (60, 840)] {
            let img = icon(sz, f)
            c.saveGState()
            var t = CGAffineTransform(scaleX: CGFloat(sz), y: CGFloat(sz)).translatedBy(x: CGFloat(x) / CGFloat(sz), y: (y0 + 40) / CGFloat(sz))
            c.addPath(mask.copy(using: &t)!); c.clip()
            c.draw(img, in: CGRect(x: CGFloat(x), y: y0 + 40, width: CGFloat(sz), height: CGFloat(sz)))
            c.restoreGState()
        }
        let attr = NSAttributedString(string: label, attributes: [.font: NSFont.systemFont(ofSize: 30, weight: .bold), .foregroundColor: NSColor(cgColor: ink)!])
        c.textPosition = CGPoint(x: 600, y: y0 + 470); CTLineDraw(CTLineCreateWithAttributedString(attr), c)
        let sub = NSAttributedString(string: "512 · 180 · 60 px", attributes: [.font: NSFont.systemFont(ofSize: 22, weight: .regular), .foregroundColor: NSColor(cgColor: ink)!])
        c.textPosition = CGPoint(x: 600, y: y0 + 432); CTLineDraw(CTLineCreateWithAttributedString(sub), c)
    }
}
save(sheet, "playbook/brand/concepts.png")
for (k, _, f) in concepts { save(icon(1024, f), "playbook/brand/concept-\(k)-1024.png") }
