import Foundation
import Observation
import CoreLocation

/// The whole app's state: the bundled places, filters, saved places and what's selected.
@MainActor
@Observable
final class AppModel {
    private(set) var places: [Place] = []
    private(set) var isLoaded = false
    private(set) var loadError: String?
    private(set) var generated = ""
    private(set) var restaurantCount = 0
    private(set) var calibration: Calibration?
    /// when Idaho State Police's alcohol license list was exported; nil until it's in the data
    private(set) var liquorUpdated: String?
    private(set) var abcLicenses = 0
    /// the Overture Maps release the listings come from, read from the data file
    private(set) var overtureRelease: String?
    /// towns sorted by how many restaurants they have
    private(set) var towns: [(name: String, count: Int)] = []
    private(set) var cuisines: [(name: String, count: Int)] = []
    /// normalized town name -> display name ("coeur d alene" -> "Coeur d'Alene")
    private(set) var townKeys: [String: String] = [:]

    var filters = Filters() { didSet { saveFilters() } }
    private(set) var saved: Set<String> = []

    // navigation (iPad sidebar / iPhone tabs)
    var selectedGuide: Guide?
    var selectedPlace: Place?
    var tab: Tab = .guides
    enum Tab: Hashable { case guides, map, saved, about }
    /// the iPhone guides stack: a guide, then a place
    var guidesPath: [Route] = []
    enum Route: Hashable { case guide(Guide), place(Place) }
    /// bumped by openGuide so the iPad sidebar follows even when the same guide is picked again
    private(set) var guideRequest = 0
    /// iPad to iPhone-size (Split View, Stage Manager): the place that was open next to the Map or Saved list, for that tab's own
    /// stack to show, so a size-class change doesn't lose it
    var handoffPlace: Place?

    /// The iPhone guides stack for what's selected: the open guide, then the open place.
    var compactPath: [Route] {
        (selectedGuide.map { [Route.guide($0)] } ?? []) + (selectedPlace.map { [Route.place($0)] } ?? [])
    }

    /// iPhone: the stack changed (a push, a pop, a swipe back), so the selection follows it; an iPad layout then opens on the same
    /// guide and place.
    func followPath() {
        var guide: Guide?
        for r in guidesPath { if case .guide(let g) = r { guide = g } }
        if selectedGuide != guide { selectedGuide = guide }
        if case .place(let p) = guidesPath.last { if selectedPlace != p { selectedPlace = p } } else if selectedPlace != nil { selectedPlace = nil }
    }

    /// Open a guide from Home: pushes it on iPhone, selects it in the iPad sidebar.
    func openGuide(_ g: Guide) {
        tab = .guides
        selectedGuide = g
        guidesPath = [.guide(g)]
        guideRequest += 1
    }

    /// a fixed "you are here" for screenshots, so lists sort by distance without a permission prompt
    var screenshotLocation: CLLocation?

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        saved = Set(defaults.stringArray(forKey: "saved") ?? [])
        if let data = defaults.data(forKey: "filters"), let f = try? JSONDecoder().decode(Filters.self, from: data) { filters = f }
    }

    /// A cold launch from Spotlight asks for the data twice (the app's .task and the search continuation); both wait on one decode.
    private var loading: Task<Void, Never>?

    func load(from url: URL? = Bundle.main.url(forResource: "places", withExtension: "json")) async {
        guard !isLoaded else { return }
        if let loading { await loading.value; return }
        let task = Task { await decode(from: url) }
        loading = task
        await task.value
    }

    private func decode(from url: URL?) async {
        guard let url else { loadError = "The restaurant data is missing from the app."; return }
        do {
            let (file, places) = try await Task.detached(priority: .userInitiated) { () throws -> (DataFile, [Place]) in
                let data = try Data(contentsOf: url)
                let file = try JSONDecoder().decode(DataFile.self, from: data)
                // kept in A-to-Z order: a filter keeps it, so the A-to-Z sort of any list is a pass over an already sorted array
                let places = file.places.map { Place($0, file: file) }
                    .sorted { $0.sortKey != $1.sortKey ? $0.sortKey < $1.sortKey : $0.id < $1.id }
                return (file, places)
            }.value
            apply(file: file, places: places)
        } catch {
            loadError = "The restaurant data couldn't be read (\(error.localizedDescription))."
        }
    }

    func apply(file: DataFile, places: [Place]) {
        self.places = places
        generated = file.generated
        restaurantCount = file.count_restaurants
        calibration = file.calibration
        liquorUpdated = file.liquor_updated
        abcLicenses = file.abc_licenses ?? 0
        overtureRelease = file.overture_release
        var tc: [String: Int] = [:], cc: [String: Int] = [:]
        for p in places where !p.isVenue {
            if let c = p.city { tc[c, default: 0] += 1 }
            cc[p.cuisine, default: 0] += 1
        }
        towns = tc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        cuisines = cc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        var keys: [String: String] = [:]
        for (name, _) in towns {   // biggest town wins a shared spelling
            // "Coeur d'Alene" is typed both ways: "coeur dalene" and "coeur d alene"
            let spaced = name.replacingOccurrences(of: "'", with: " ").replacingOccurrences(of: "\u{2019}", with: " ")
            for k in Set([Search.normalizeAddress(name), Search.normalizeAddress(spaced)]) where keys[k] == nil { keys[k] = name }
        }
        if let cda = towns.first(where: { $0.name == "Coeur d'Alene" })?.name, keys["cda"] == nil { keys["cda"] = cda }   // the local short form
        townKeys = keys
        if let t = filters.town, tc[t] == nil { filters.town = nil }
        if let c = filters.cuisine, cc[c] == nil { filters.cuisine = nil }
        isLoaded = true
    }

    func place(id: String) -> Place? { places.first { $0.id == id } }

    /// The last list asked for. A list view's body runs on every change (an iPad row tap re-renders it), so the same guide, sort,
    /// search, filters and (for a distance sort) location to ~100 m reuse the result instead of filtering 17,000 places again.
    private struct ListKey: Equatable {
        let guide: Guide, sort: SortOrder, search: String, filters: Filters, count: Int, lat: Int?, lon: Int?
    }
    @ObservationIgnored private var lastList: (key: ListKey, places: [Place])?

    /// Places in a guide, filtered and searched, in the chosen order.
    func list(_ guide: Guide, sort: SortOrder, search: String, here: CLLocation?) -> [Place] {
        // reading filters and places here keeps SwiftUI observing them even when the cached list is returned
        let usesHere = sort == .nearest || guide == .nearMe
        let key = ListKey(guide: guide, sort: sort, search: search, filters: filters, count: places.count,
                          lat: usesHere ? here.map { Int(($0.coordinate.latitude * 1000).rounded()) } : nil,
                          lon: usesHere ? here.map { Int(($0.coordinate.longitude * 1000).rounded()) } : nil)
        if let lastList, lastList.key == key { return lastList.places }
        let out = makeList(guide, sort: sort, search: search, here: usesHere ? here : nil)
        lastList = (key, out)
        return out
    }

    private func makeList(_ guide: Guide, sort: SortOrder, search: String, here: CLLocation?) -> [Place] {
        let q = Search.parse(search, towns: townKeys)
        // typed something, but nothing searchable ("🍕", "!!!"): show nothing rather than everything
        if q.isEmpty && !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return [] }
        var out = places.filter { guide.includes($0) && filters.allows($0) && (q.isEmpty || Search.matches($0, q)) }
        if guide == .nearMe && here == nil { return [] }
        out = Ranking.sort(out, by: sort, from: here)
        if !q.tokens.isEmpty && !(guide.isRanked) {   // name matches first when searching
            let named = out.filter { Search.nameMatches($0, q) }
            if !named.isEmpty && named.count < out.count {
                let ids = Set(named.map(\.id))
                out = named + out.filter { !ids.contains($0.id) }
            }
        }
        return out
    }

    func count(_ guide: Guide) -> Int { places.lazy.filter { guide.includes($0) && self.filters.allows($0) }.count }

    // MARK: saved places

    func isSaved(_ p: Place) -> Bool { saved.contains(p.id) }

    func toggleSaved(_ p: Place) {
        if saved.contains(p.id) { saved.remove(p.id) } else { saved.insert(p.id) }
        defaults.set(Array(saved).sorted(), forKey: "saved")
    }

    var savedPlaces: [Place] { places.filter { saved.contains($0.id) }.sorted { $0.sortKey != $1.sortKey ? $0.sortKey < $1.sortKey : $0.id < $1.id } }

    /// A random place from a guide ("Surprise me"), never the one just shown.
    func randomPick(from guide: Guide, excluding last: String?) -> Place? {
        let pool = places.filter { guide.includes($0) && filters.allows($0) && $0.id != last }
        return pool.randomElement()
    }

    private func saveFilters() {
        if let data = try? JSONEncoder().encode(filters) { defaults.set(data, forKey: "filters") }
    }

    // MARK: honest labels

    /// "76%": how often a map listing of this kind matched a licensed business in Denver, where every food business is licensed
    /// (Colorado's test of the same Overture release). Idaho has no complete official list to measure against.
    func matchRate(for p: Place) -> String? {
        guard p.tier != .licensed else { return nil }   // an official record confirms it; no listing rate needed
        let group: String
        switch (p.source, p.tier) {
        case ("meta", .confirmed): group = "meta_high"
        case ("meta", _): group = "meta_mid"
        case ("AllThePlaces", _), ("DAC", _): group = "brand_feed"
        default: return nil
        }
        guard let v = calibration?.reference_colorado_denver?.groups?[group]?.official else { return nil }
        return "\(Int((v * 100).rounded()))%"
    }
}
