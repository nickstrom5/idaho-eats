import SwiftUI

/// Idaho landscape palette, light only (no team colors: fans split between Boise State, the Vandals and Idaho State):
/// huckleberry #4B2A5C (10.7:1 on the cream), Sawtooth pine #2E5A4C (7.1:1), cream #F8F4EC, and russet #C9A06B only as a fill under
/// dark text (russet text on cream is 2.2:1 and fails). The names `green`/`gold` are kept from Wisconsin Eats so the shared views read
/// the same; here `green` is huckleberry and `gold` is russet.
enum Theme {
    static let green = Color(hex: 0x4B2A5C)      // huckleberry: titles, tint, primary text accents
    static let green2 = Color(hex: 0x2E5A4C)     // Sawtooth pine
    static let gold = Color(hex: 0xC9A06B)       // russet: fills only
    static let goldSoft = Color(hex: 0xEFE1C8)
    static let goldEdge = Color(hex: 0xB08550)   // the Idaho guide cards' border
    static let pine = Color(hex: 0x2E5A4C)
    static let ink = Color(hex: 0x1F1A24)
    static let ink2 = Color(hex: 0x3A3342)
    static let muted = Color(hex: 0x5E5668)
    static let cream = Color(hex: 0xF8F4EC)
    static let surface = Color(hex: 0xFFFDF9)
    static let surface2 = Color(hex: 0xF1ECE2)
    static let surface3 = Color(hex: 0xE5DDCF)
    static let rule = Color(hex: 0xE2DACC)
    static let rule2 = Color(hex: 0xC7BBA8)
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

/// A small uppercase label: "FINGER STEAKS", "JAMES BEARD WINNER".
struct Chip: View {
    enum Style { case gold, green, pine, plain, dashed }
    let text: String
    var style: Style = .plain

    var body: some View {
        Text(text.uppercased())
            .font(.caption2.weight(.bold))
            .tracking(0.4)
            .padding(.horizontal, 7).padding(.vertical, 3)
            .foregroundStyle(style == .green || style == .pine ? Color.white : style == .dashed ? Theme.muted : Theme.green)
            .background {
                RoundedRectangle(cornerRadius: 5).fill(style == .gold ? Theme.goldSoft : style == .green ? Theme.green : style == .pine ? Theme.pine
                                                       : style == .dashed ? .clear : Theme.surface2)
            }
            .overlay {
                if style == .dashed { RoundedRectangle(cornerRadius: 5).strokeBorder(Theme.rule2, style: StrokeStyle(lineWidth: 1, dash: [3, 2])) }
            }
            .accessibilityLabel(text)
    }
}

/// The Sawtooths, drawn once under the Home header: sharp granite teeth with three snow caps, over a huckleberry line.
struct RidgeLine: View {
    static let peaks: [(CGFloat, CGFloat)] = [(0, 0.62), (0.05, 0.42), (0.08, 0.55), (0.13, 0.18), (0.17, 0.44), (0.21, 0.30), (0.25, 0.50),
                                              (0.31, 0.06), (0.35, 0.36), (0.39, 0.24), (0.44, 0.52), (0.50, 0.14), (0.54, 0.40),
                                              (0.59, 0.28), (0.64, 0.55), (0.70, 0.10), (0.74, 0.38), (0.79, 0.26), (0.85, 0.52),
                                              (0.90, 0.22), (0.95, 0.45), (1, 0.36)]
    var body: some View {
        Canvas { ctx, size in
            let w = size.width, h = size.height
            var ridge = Path()
            ridge.move(to: CGPoint(x: 0, y: h))
            for (x, y) in Self.peaks { ridge.addLine(to: CGPoint(x: x * w, y: y * h)) }
            ridge.addLine(to: CGPoint(x: w, y: h)); ridge.closeSubpath()
            ctx.fill(ridge, with: .color(Theme.pine))
            ctx.clip(to: ridge)   // the snow stays inside the granite
            for (x, y) in [(0.31, 0.06), (0.70, 0.10), (0.50, 0.14)] as [(CGFloat, CGFloat)] {
                var cap = Path()
                cap.move(to: CGPoint(x: x * w, y: y * h))
                cap.addLine(to: CGPoint(x: x * w - h * 0.40, y: (y + 0.34) * h))
                cap.addLine(to: CGPoint(x: x * w - h * 0.10, y: (y + 0.24) * h))
                cap.addLine(to: CGPoint(x: x * w + h * 0.06, y: (y + 0.34) * h))
                cap.addLine(to: CGPoint(x: x * w + h * 0.36, y: (y + 0.30) * h))
                cap.closeSubpath()
                ctx.fill(cap, with: .color(.white.opacity(0.9)))
            }
            ctx.fill(Path(CGRect(x: 0, y: h - 3, width: w, height: 3)), with: .color(Theme.green))
        }
        .accessibilityHidden(true)
    }
}

/// Condensed, heavy display type for titles and big numbers (the system font's compressed width). It scales with the
/// reader's text size, capped at 1.6× so a big number can't swallow its row.
struct DisplayFont: ViewModifier {
    let size: CGFloat
    var weight: Font.Weight = .black
    @ScaledMetric(relativeTo: .body) private var scale: CGFloat = 1

    func body(content: Content) -> some View {
        content.font(.system(size: size * min(scale, 1.6), weight: weight).width(.compressed))
    }
}

extension View {
    func displayFont(_ size: CGFloat, weight: Font.Weight = .black) -> some View {
        modifier(DisplayFont(size: size, weight: weight))
    }
}

extension View {
    /// An inline navigation title in the display type. UINavigationBar.appearance() didn't reach every SwiftUI bar on iOS 27
    /// (the Map title went from compressed blue to plain black after a push and pop; place titles were always plain), so the
    /// title is our own view in the bar. The navigation title is still set, for the back button and VoiceOver.
    func inlineTitle(_ title: String) -> some View {
        navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text(title).displayFont(19, weight: .heavy).foregroundStyle(Theme.green)
                        .lineLimit(1).minimumScaleFactor(0.7)
                        .accessibilityAddTraits(.isHeader)
                }
            }
    }
}
