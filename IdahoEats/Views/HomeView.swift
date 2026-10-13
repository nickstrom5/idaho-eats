import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var lastRandom: String?
    private let columns = [GridItem(.adaptive(minimum: 158), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                Button { model.openGuide(.all) } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").foregroundStyle(Theme.green)
                        Text("Search by name, town or street").foregroundStyle(Theme.muted)
                        Spacer()
                    }
                    .font(.subheadline)
                    .padding(14)
                    .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.green, lineWidth: 2))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Search every restaurant")
                LazyVGrid(columns: columns, spacing: 12) {
                    // a guide with no places yet (research still coming in) gets no card
                    ForEach(Self.cards.filter { $0 == .nearMe || model.count($0) > 0 }) { g in
                        Button { model.openGuide(g) } label: { GuideCard(guide: g, count: model.count(g)) }
                            .buttonStyle(.plain)
                    }
                }
                surpriseButton
                Text(model.abcLicenses > 0
                     ? "Ratings, hours and photos come live from Apple Maps on each place. Lists are built from open map data, Idaho State Police alcohol licenses and hand-checked research. Idaho's health districts don't publish inspection results in bulk, so there are none here. See About for sources."
                     : "Ratings, hours and photos come live from Apple Maps on each place. Lists are built from open map data and hand-checked research. Idaho's health districts don't publish inspection results in bulk, so there are none here. See About for sources.")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
            .padding(16)
        }
        .background(Theme.cream)
        .navigationTitle("")
        .toolbar(.hidden, for: .navigationBar)
    }

    static let cards: [Guide] = [.basque, .fingerSteaks, .spuds, .huckleberry, .trout, .taquerias, .historic, .honors, .oldest, .nearMe]

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("IDAHO\nEATS")
                .displayFont(52)
                .foregroundStyle(Theme.green)
                .lineSpacing(-6)
                .accessibilityAddTraits(.isHeader)
            RidgeLine().frame(height: 22).padding(.bottom, 4)
            Text("Finger steaks, Basque & spud guide")
                .font(.headline).foregroundStyle(Theme.ink)
            Text("Hand-checked Basque kitchens, finger steaks and drive-ins, spud plates, huckleberry, trout and the oldest places, plus \(model.restaurantCount.formatted()) restaurants in \(model.towns.count.formatted()) towns.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
        }
        .padding(.top, 8)
    }

    private var surpriseButton: some View {
        Button {
            if let p = model.randomPick(from: .fingerSteaks, excluding: lastRandom) {
                lastRandom = p.id
                // iPhone pushes it; iPad shows it in the place column (a growing stack there would resurface after a size change)
                if sizeClass != .regular { model.guidesPath.append(.place(p)) }
                model.selectedPlace = p
            }
        } label: {
            Label("Surprise me with a finger steak spot", systemImage: "dice")
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity).padding(12)
                .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.rule2))
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.ink)
    }
}

struct GuideCard: View {
    let guide: Guide
    let count: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: guide.systemImage).font(.title3).foregroundStyle(Theme.green)
                    .frame(width: 36, height: 36).background(Circle().fill(guide.isIdaho ? Theme.goldSoft : Theme.surface2))
                Spacer()
                if guide != .nearMe && guide != .all {   // "All" would just repeat the total in the header; Near Me has no fixed count
                    Text(count.formatted()).displayFont(22).foregroundStyle(Theme.green).monospacedDigit()
                }
            }
            Text(guide.title).displayFont(22, weight: .heavy).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
            Text(guide.subtitle).font(.caption).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 150, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(guide.isIdaho ? Theme.goldEdge : Theme.rule))
        // one reading of the count, after the title ("Basque. Boise's Basque Block …", "12 places")
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(guide.title). \(guide.subtitle)")
        .accessibilityValue(guide != .nearMe && guide != .all ? "\(count) \(count == 1 ? "place" : "places")" : "")
    }
}
