import Foundation
import CoreLocation
import SwiftUI

// MARK: - The bundled data file (Resources/places.json), written by pipeline/idaho.py with ID_APP=1

struct DataFile: Decodable {
    let generated: String
    /// the Overture Maps release the listings come from ("2026-09-23.1"); optional so an older file still opens
    let overture_release: String?
    /// when Idaho State Police's alcohol license list was exported; nil until it's in the data
    let liquor_updated: String?
    let abc_licenses: Int?
    let cities: [String]
    let cuisines: [String]
    let brands: [String]
    let counties: [String]
    let srcs: [String]
    let count_restaurants: Int
    let calibration: Calibration?
    let places: [PlaceRecord]
}

/// What the app can say about how listings were checked (pipeline/calibrate.py). Nothing Google-derived: Idaho's own match rates
/// against ISP alcohol licenses, and Colorado's test against Denver's full food-license list (same Overture release) for reference.
struct Calibration: Decodable, Hashable {
    let groups: [String: CalibrationGroup]?
    let reference_colorado_denver: Reference?
    let abc_found_in_listings: Double?

    struct Reference: Decodable, Hashable {
        let groups: [String: DenverGroup]?
    }
    struct DenverGroup: Decodable, Hashable {
        let n: Int
        let official: Double
    }
}

struct CalibrationGroup: Decodable, Hashable {
    let n: Int
    /// share of Idaho listings of this kind on an on-premises alcohol license (a lower bound: many restaurants don't serve alcohol)
    let abc_onprem: Double?
}

/// An official record behind a place: an Idaho State Police alcohol license.
struct LicenseRecord: Decodable, Hashable {
    let src: String
    let id: String
    let type: String?
    let exp: String?
}

struct PlaceRecord: Decodable {
    let id: String
    let n: String
    let c: Int?
    let cu: Int
    let t: Int
    let s: Int
    let co: Int?
    let a: String?
    let z: String?
    let la: Double?
    let lo: Double?
    let b: Int?
    let ch: Int?
    let j: Int?
    let v: Int?
    let bar: Int?
    let g: Int?
    let hc: Int?
    let h: Int?
    let jbf: String?
    let ip: Double?
    let f: Int?
    let fn: String?
    let note: String?
    let dish: String?
    let seas: String?
    let liq: String?
    let w: String?
    let ph: String?
    let lic: [LicenseRecord]?
}

// MARK: - The model the views use

struct PlaceTags: OptionSet, Hashable {
    let rawValue: Int
    // the guide tags are set only on hand-checked places (open, with a 2025–26 source); the order is pipeline/idaho.py's TAGS
    static let basque = PlaceTags(rawValue: 1)
    static let fingerSteaks = PlaceTags(rawValue: 2)
    static let driveIn = PlaceTags(rawValue: 4)
    static let spud = PlaceTags(rawValue: 8)
    static let huckleberry = PlaceTags(rawValue: 16)
    static let trout = PlaceTags(rawValue: 32)
    static let taqueria = PlaceTags(rawValue: 64)
    static let historic = PlaceTags(rawValue: 128)    // historic saloon or supper club
    static let oldest = PlaceTags(rawValue: 256)      // open at this address since 1960 or earlier
    static let resortTown = PlaceTags(rawValue: 512)  // any place in a resort town (not hand-checked)

    static let guides: PlaceTags = [.basque, .fingerSteaks, .driveIn, .spud, .huckleberry, .trout, .taqueria, .historic, .oldest]
}

/// How a place got on the list. The share that matched an official record comes from calibration.
enum Tier: Int, Comparable {
    case listing = 0        // one map listing
    case confirmed = 1      // a high-confidence Meta listing, or a hand-checked place
    case licensed = 2       // on an Idaho State Police alcohol license

    static func < (a: Tier, b: Tier) -> Bool { a.rawValue < b.rawValue }

    var label: String {
        switch self {
        case .licensed: "On an official record"
        case .confirmed: "Confirmed listing"
        case .listing: "Listing only"
        }
    }
}

enum Jurisdiction: Int {
    case none = 0, abc = 1
    var listName: String {
        switch self {
        case .abc: "Idaho State Police alcohol licenses (Alcohol Beverage Control)"
        case .none: ""
        }
    }
}

struct Place: Identifiable, Hashable {
    let id: String
    let name: String
    let address: String?
    let city: String?
    let county: String?
    let zip: String?
    let coordinate: CLLocationCoordinate2D?
    let cuisine: String
    let brand: String?
    let chainCount: Int
    let tier: Tier
    let jurisdiction: Jurisdiction
    let source: String
    let isVenue: Bool
    let isBar: Bool
    let tags: PlaceTags
    /// On our hand-checked list (data/research): confirmed open with a 2025–26 source.
    let handChecked: Bool
    let honorFlags: Int
    let iconicPoints: Double?
    let jamesBeard: String?
    let founded: Int?
    let foundedNote: String?
    let note: String?
    let dishes: String?
    let seasonal: String?
    /// on-premises ISP alcohol license type; nil means unknown, not "no"
    let liquor: String?
    let website: URL?
    let phone: String?
    let licenses: [LicenseRecord]
    /// normalized text for search: name, town, county, zip, cuisine, brand, dishes, then the address with street words abbreviated
    let searchText: String
    let nameText: String
    /// the A-to-Z key, worked out once at load: the normalized name ("por wine house" for "/pôr/ Wine House"), so case, accents
    /// and leading punctuation don't change the order, and a sort never runs a localized compare per comparison
    let sortKey: String
    /// made once at load: a new CLLocation per comparison made a Nearest sort of 16,000 places take seconds
    let location: CLLocation?

    static func == (a: Place, b: Place) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }

    /// James Beard or a verified founding year: what the map and Spotlight put first (Idaho has no MICHELIN Guide)
    var isHonored: Bool { honorFlags != 0 }
    /// what the Honors section lists: a James Beard honor ("oldest" alone isn't an honor)
    var hasHonors: Bool { jamesBeard != nil }
    var isChain: Bool { chainCount >= 5 }
    var jamesBeardLabel: String? {
        if honorFlags & 1 != 0 { return "America's Classic" }
        if honorFlags & 2 != 0 { return "James Beard winner" }
        if honorFlags & 4 != 0 { return "James Beard nominee" }
        if honorFlags & 8 != 0 { return "James Beard semifinalist" }
        return nil
    }
    /// The chip for a James Beard line: the place's own honor, or a restaurateur (group) honor when that's the only one.
    var jamesBeardChip: String? { jamesBeardLabel ?? (jamesBeard != nil ? "James Beard (restaurateur)" : nil) }
    /// a hand-checked Idaho pick: the gold pins
    var isClassic: Bool { handChecked && !tags.isDisjoint(with: .guides) }
    var townLine: String { [city, cuisine].compactMap { $0 }.joined(separator: " · ") }
    var fullAddress: String {
        [address, [city, zip].compactMap { $0 }.joined(separator: " ")].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", ")
    }

    /// "Serves alcohol", from Idaho State Police's alcohol licenses: never a bare dash that reads as "no". An on-premises license
    /// (liquor by the drink, beer or wine served there) or a brewery, winery or distillery license says yes.
    var servesAlcohol: String {
        if let liquor { return "Yes · \(liquor)" }
        if !licenses.isEmpty { return "Beer or wine to go only (store license)" }
        return "Unknown (no on-premises alcohol license matched)"
    }

    init(_ r: PlaceRecord, file: DataFile) {
        let city = r.c.flatMap { $0 < file.cities.count ? file.cities[$0] : nil }
        let cuisine = r.cu < file.cuisines.count ? file.cuisines[r.cu] : "American & Other"
        let brand = r.b.flatMap { $0 < file.brands.count ? file.brands[$0] : nil }
        let county = r.co.flatMap { $0 < file.counties.count ? file.counties[$0] : nil }
        id = r.id
        name = r.n
        address = r.a
        self.city = city
        self.county = county
        zip = r.z
        if let la = r.la, let lo = r.lo { coordinate = CLLocationCoordinate2D(latitude: la, longitude: lo) } else { coordinate = nil }
        self.cuisine = cuisine
        self.brand = brand
        chainCount = r.ch ?? 1
        tier = Tier(rawValue: r.t) ?? .listing
        jurisdiction = Jurisdiction(rawValue: r.j ?? 0) ?? .none
        source = r.s < file.srcs.count ? file.srcs[r.s] : "meta"
        isVenue = r.v == 1
        isBar = r.bar == 1
        tags = PlaceTags(rawValue: r.g ?? 0)
        handChecked = r.hc == 1
        honorFlags = r.h ?? 0
        iconicPoints = r.ip
        jamesBeard = r.jbf
        founded = r.f
        foundedNote = r.fn
        note = r.note
        dishes = r.dish
        seasonal = r.seas
        liquor = r.liq
        // web links only: a bare host gets https://, and any other scheme (javascript:, tel:, a custom app URL) is dropped
        website = r.w.flatMap { URL(string: $0.contains("://") ? $0 : "https://" + $0) }
            .flatMap { ["http", "https"].contains($0.scheme?.lowercased() ?? "") && $0.host != nil ? $0 : nil }
        phone = r.ph
        licenses = r.lic ?? []
        // the dishes a hand-checked place serves are searchable too: "finger steaks boise", "huckleberry shake"
        // a town with an apostrophe is searchable with a space too ("coeur d alene")
        let spacedCity = city.flatMap { $0.contains("'") ? $0.replacingOccurrences(of: "'", with: " ") : nil }
        searchText = " " + Search.normalize([r.n, city, spacedCity, county, r.z, cuisine, brand, r.dish].compactMap { $0 }.joined(separator: " ")) + " "
            + Search.normalizeAddress(r.a ?? "") + " "
        nameText = " " + Search.normalize([r.n, brand].compactMap { $0 }.joined(separator: " ")) + " "
        sortKey = Search.normalize(r.n)
        location = coordinate.map { CLLocation(latitude: $0.latitude, longitude: $0.longitude) }
    }
}

/// The data's dates are calendar days ("2026-06-16"), not moments: read and shown in UTC, so no time zone can move one a day.
enum DayFormat {
    private static let utc = TimeZone(identifier: "UTC")!

    static func date(_ s: String?) -> Date? {
        guard let s, s.count >= 10 else { return nil }
        let parts = s.prefix(10).split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3, (1...12).contains(parts[1]), (1...31).contains(parts[2]) else { return nil }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = utc
        return cal.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2]))
    }

    /// "Jun 16, 2026" (in the reader's language); anything that isn't a date is shown as it is
    static func text(_ s: String?) -> String? {
        guard let s else { return nil }
        guard let d = date(s) else { return s }
        return d.formatted(Date.FormatStyle(date: .abbreviated, time: .omitted, timeZone: utc))
    }

    /// "Sep 2025"
    static func monthYear(_ s: String?) -> String? {
        guard let s else { return nil }
        guard let d = date(s) else { return s }
        return d.formatted(Date.FormatStyle(timeZone: utc).month(.abbreviated).year())
    }
}
