import Foundation
import CoreLocation

/// The lists the app is built around. Each is a filter plus an order; none uses ratings (the app only publishes data it may).
enum Guide: String, CaseIterable, Identifiable, Hashable {
    case basque, fingerSteaks, spuds, huckleberry, trout, taquerias, historic, honors, oldest, nearMe, all

    var id: String { rawValue }

    var title: String {
        switch self {
        case .basque: "Basque"
        case .fingerSteaks: "Finger Steaks & Drive-Ins"
        case .spuds: "Spud Plates"
        case .huckleberry: "Huckleberry"
        case .trout: "Idaho Trout"
        case .taquerias: "Taquerías"
        case .historic: "Historic Saloons"
        case .honors: "James Beard Honors"
        case .oldest: "Oldest Places"
        case .nearMe: "Near Me"
        case .all: "All Restaurants"
        }
    }

    var subtitle: String {
        switch self {
        case .basque: "Boise's Basque Block and Basque kitchens around the state, hand-checked"
        case .fingerSteaks: "Finger steaks, fry sauce and drive-in burgers, hand-checked"
        case .spuds: "Potato plates named on the menu, hand-checked"
        case .huckleberry: "Huckleberry shakes, pies and pancakes, hand-checked"
        case .trout: "Idaho rainbow trout on the menu, hand-checked"
        case .taquerias: "Taquerías with a fixed address, hand-checked"
        case .historic: "Old saloons and supper clubs, hand-checked"
        case .honors: "James Beard winners, nominees, semifinalists and America's Classics"
        case .oldest: "Founding years checked at the same address, oldest first"
        case .nearMe: "Everything around you, closest first"
        case .all: "Restaurants, cafés, bars and bakeries statewide"
        }
    }

    var systemImage: String {
        switch self {
        case .basque: "wineglass"
        case .fingerSteaks: "car"
        case .spuds: "fork.knife.circle"
        case .huckleberry: "birthday.cake"
        case .trout: "fish"
        case .taquerias: "takeoutbag.and.cup.and.straw"
        case .historic: "building.columns"
        case .honors: "star.circle"
        case .oldest: "clock.arrow.circlepath"
        case .nearMe: "location"
        case .all: "fork.knife"
        }
    }

    /// The Idaho food guides get the gold card on Home.
    var isIdaho: Bool { [.basque, .fingerSteaks, .spuds, .huckleberry, .trout, .taquerias, .historic].contains(self) }

    /// Guides whose order is a ranking worth numbering.
    var isRanked: Bool { [.oldest].contains(self) }

    var sortOptions: [SortOrder] {
        switch self {
        case .basque, .fingerSteaks, .spuds, .huckleberry, .trout, .taquerias, .historic: [.featured, .nearest, .name]
        case .honors: [.iconic, .nearest]
        case .oldest: [.oldest]
        case .nearMe: [.nearest]
        case .all: [.name, .nearest]
        }
    }

    var defaultSort: SortOrder { sortOptions[0] }

    func includes(_ p: Place) -> Bool {
        switch self {
        // the guides that promise "hand-checked" list only places checked open with a 2025–26 source
        case .basque: p.handChecked && p.tags.contains(.basque)
        case .fingerSteaks: p.handChecked && !p.tags.isDisjoint(with: [.fingerSteaks, .driveIn])
        case .spuds: p.handChecked && p.tags.contains(.spud)
        case .huckleberry: p.handChecked && p.tags.contains(.huckleberry)
        case .trout: p.handChecked && p.tags.contains(.trout)
        case .taquerias: p.handChecked && p.tags.contains(.taqueria)
        case .historic: p.handChecked && p.tags.contains(.historic)
        case .honors: p.jamesBeard != nil
        case .oldest: p.founded != nil
        case .nearMe, .all: true
        }
    }
}

enum SortOrder: String, CaseIterable, Identifiable {
    case featured, nearest, oldest, name, iconic
    var id: String { rawValue }
    var label: String {
        switch self {
        case .featured: "Featured first"
        case .nearest: "Nearest"
        case .oldest: "Oldest first"
        case .name: "A to Z"
        case .iconic: "By James Beard honor"
        }
    }
}

/// Filters shared by every list. Search text lives with each list.
struct Filters: Equatable, Codable {
    var town: String?
    var cuisine: String?
    var hideChains = false
    var confirmedOnly = false
    var includeNonRestaurants = false

    var activeCount: Int {
        [town != nil, cuisine != nil, hideChains, confirmedOnly, includeNonRestaurants].filter { $0 }.count
    }

    func allows(_ p: Place) -> Bool {
        if !includeNonRestaurants && p.isVenue { return false }
        if let town, p.city != town { return false }
        if let cuisine, p.cuisine != cuisine { return false }
        if hideChains && p.isChain { return false }
        if confirmedOnly && p.tier == .listing { return false }
        return true
    }
}

enum Ranking {
    static func sort(_ places: [Place], by order: SortOrder, from here: CLLocation?) -> [Place] {
        // Keys come from fields made once at load: a localized compare, or a new CLLocation per comparison, made a 16,000-place
        // sort take most of a second (AR-13). sortKey is the normalized name, so case, accents and punctuation don't change the order.
        func name(_ a: Place, _ b: Place) -> Bool { a.sortKey != b.sortKey ? a.sortKey < b.sortKey : a.id < b.id }
        switch order {
        case .nearest where here != nil:
            // each distance once, not four times per comparison
            let from = here!
            return places.map { p in (p, p.location.map { $0.distance(from: from) } ?? .greatestFiniteMagnitude) }
                .sorted { $0.1 != $1.1 ? $0.1 < $1.1 : name($0.0, $1.0) }
                .map(\.0)
        case .featured, .nearest:
            // honored places first, then verified founding year, then name
            return places.sorted {
                let a = $0.iconicPoints ?? -1, b = $1.iconicPoints ?? -1
                if a != b { return a > b }
                let fa = $0.founded ?? 9999, fb = $1.founded ?? 9999
                return fa != fb ? fa < fb : name($0, $1)
            }
        case .oldest:
            return places.sorted { ($0.founded ?? 9999) != ($1.founded ?? 9999) ? ($0.founded ?? 9999) < ($1.founded ?? 9999) : name($0, $1) }
        case .name:
            return places.sorted(by: name)
        case .iconic:
            // an order anyone can check: the James Beard honor (America's Classic, winner, nominee, semifinalist), then name
            func jb(_ p: Place) -> Int { p.honorFlags & 1 != 0 ? 4 : p.honorFlags & 2 != 0 ? 3 : p.honorFlags & 4 != 0 ? 2 : p.honorFlags & 8 != 0 ? 1 : 0 }
            return places.sorted { jb($0) != jb($1) ? jb($0) > jb($1) : name($0, $1) }
        }
    }
}
