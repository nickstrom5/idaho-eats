import XCTest
import CoreLocation
@testable import IdahoEats

@MainActor
final class IdahoEatsTests: XCTestCase {

    /// A tiny data file with the same shape as Resources/places.json. The places are fictional; the real ones are checked in
    /// testBundledData.
    private func sampleModel() async throws -> AppModel {
        let json = """
        {"v":1,"generated":"2026-10-08","liquor_updated":"2026-10-08","abc_licenses":4000,
         "cities":["Boise","Meridian","Nampa","Idaho Falls","Sandpoint","Ketchum","Hagerman","Caldwell","Coeur d'Alene","Pocatello"],
         "cuisines":["Basque","Burgers","Coffee & Café","American & Other","Seafood","Mexican","Bar & Pub"],
         "brands":["Dutch Bros"],"counties":["Ada County","Canyon County","Bonneville County","Bonner County","Blaine County","Gooding County","Kootenai County","Bannock County"],
         "srcs":["official","meta","AllThePlaces","DAC","research"],"count":11,"count_restaurants":10,
         "calibration":{"groups":{"meta >= 0.95":{"n":3090,"abc_onprem":0.21}},
                        "reference_colorado_denver":{"groups":{"meta_high":{"n":1885,"official":0.759},"meta_mid":{"n":342,"official":0.319}}}},
         "places":[
          {"id":"a","n":"Grove Street Basque Bar","c":0,"co":0,"cu":0,"t":2,"s":1,"hc":1,"a":"200 Grove St","z":"83702","la":43.6139,"lo":-116.2028,"j":1,"g":1,
           "dish":"chorizo; croquetas","liq":"Liquor by the drink","lic":[{"src":"Idaho ABC license","id":"1234","type":"Liquor by the drink","exp":"2027-04-30"}]},
          {"id":"b","n":"Bench Drive-In","c":0,"co":0,"cu":1,"t":1,"s":1,"hc":1,"a":"1900 W State St","la":43.6260,"lo":-116.2200,"g":6,"dish":"finger steaks; fry sauce"},
          {"id":"c","n":"Dutch Bros","c":1,"co":0,"cu":2,"t":1,"s":2,"b":0,"ch":44,"la":43.61,"lo":-116.39},
          {"id":"d","n":"Finger Steak Shack","c":2,"co":1,"cu":1,"t":0,"s":1,"a":"100 12th Ave S","la":43.58,"lo":-116.56},
          {"id":"e","n":"Maverik","c":3,"co":2,"cu":3,"t":1,"s":1,"v":1,"la":43.49,"lo":-112.03},
          {"id":"f","n":"Lakeside Huckleberry Cafe","c":4,"co":3,"cu":2,"t":1,"s":1,"hc":1,"a":"5 Lake St","la":48.276,"lo":-116.553,"g":16,"seas":"summer only"},
          {"id":"g","n":"Wood River Saloon","c":5,"co":4,"cu":6,"t":1,"s":1,"hc":1,"a":"300 N Main St","la":43.682,"lo":-114.364,"g":904,"h":17,"ip":56,"f":1950,
           "jbf":"America's Classics 2025","dish":"loaded baked potato"},
          {"id":"h","n":"Hagerman Trout House","c":6,"co":5,"cu":4,"t":1,"s":1,"hc":1,"a":"10 State St","la":42.81,"lo":-114.90,"g":32,"dish":"rainbow trout"},
          {"id":"i","n":"Canyon Taqueria","c":7,"co":1,"cu":5,"t":1,"s":1,"hc":1,"a":"700 Main St","la":43.662,"lo":-116.687,"g":64,"h":2,"ip":40,
           "jbf":"Best Chef: Mountain winner 2025 (A. Chef)"},
          {"id":"j","n":"Old Brew Works","c":8,"co":6,"cu":6,"t":2,"s":1,"a":"10 Sherman Ave","la":47.676,"lo":-116.78,"j":1,"liq":"Brewery",
           "lic":[{"src":"Idaho ABC license","id":"5678","type":"Brewery","exp":"2027-02-28"}]},
          {"id":"k","n":"Corner Spirits","c":9,"co":7,"cu":3,"t":2,"s":0,"v":1,"a":"20 Main St","la":42.86,"lo":-112.44,"j":1,
           "lic":[{"src":"Idaho ABC license","id":"9999","type":"Beer and wine (off premises)","exp":null}]}
         ]}
        """
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("places-test.json")
        try json.data(using: .utf8)!.write(to: url)
        let model = AppModel(defaults: UserDefaults(suiteName: "test-\(UUID().uuidString)")!)
        await model.load(from: url)
        XCTAssertTrue(model.isLoaded, model.loadError ?? "")
        return model
    }

    func testDecodesAndHidesNonRestaurantsByDefault() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.places.count, 11)
        XCTAssertEqual(m.liquorUpdated, "2026-10-08")
        let all = m.list(.all, sort: .name, search: "", here: nil)
        XCTAssertFalse(all.contains { $0.name == "Maverik" }, "gas-station counters are hidden unless asked for")
        m.filters.includeNonRestaurants = true
        XCTAssertTrue(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Maverik" })
    }

    func testGuidesListOnlyWhatTheyPromise() async throws {
        let m = try await sampleModel()
        func ids(_ g: Guide, _ sort: IdahoEats.SortOrder = .name) -> [String] { m.list(g, sort: sort, search: "", here: nil).map(\.id) }
        XCTAssertEqual(ids(.fingerSteaks), ["b"], "a listing merely named \u{201C}Finger Steak\u{201D} isn't hand-checked, so it stays out of the guide")
        XCTAssertEqual(m.list(.all, sort: .name, search: "finger steak shack", here: nil).map(\.id), ["d"], "but it's still in the directory")
        XCTAssertEqual(ids(.basque), ["a"])
        XCTAssertEqual(ids(.spuds), ["g"])
        XCTAssertEqual(ids(.huckleberry), ["f"])
        XCTAssertEqual(ids(.trout), ["h"])
        XCTAssertEqual(ids(.taquerias), ["i"])
        XCTAssertEqual(ids(.historic), ["g"])
        XCTAssertEqual(ids(.honors, .iconic), ["g", "i"], "an America's Classic comes before a winner: an order anyone can check")
        XCTAssertEqual(ids(.oldest, .oldest), ["g"])
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: nil), [], "near me needs a location")
    }

    /// Idaho publishes no inspection results in bulk: no guide claims any, and each county maps to the district that inspects it.
    func testNoInspectionsAndEveryCountyHasADistrict() {
        XCTAssertFalse(Guide.allCases.contains { $0.title.localizedCaseInsensitiveContains("inspection") })
        XCTAssertEqual(HealthDistrict.of(county: "Ada County")?.name, "Central District Health")
        XCTAssertNil(HealthDistrict.of(county: "Canyon County")?.lookup, "Southwest District Health has no online lookup")
        XCTAssertNil(HealthDistrict.of(county: "Spokane County"))
        XCTAssertEqual(Set(HealthDistrict.all.values.map(\.name)).count, 7, "seven districts")
        XCTAssertEqual(HealthDistrict.all.count, 44, "all 44 of Idaho's counties")
    }

    /// Calendar days stay the same day in every time zone, and read as dates, not ISO strings.
    func testDatesAreCalendarDays() {
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        let d = DayFormat.date("2026-06-16")!
        XCTAssertEqual(utc.dateComponents([.year, .month, .day], from: d), DateComponents(year: 2026, month: 6, day: 16))
        let text = DayFormat.text("2026-06-16")!
        XCTAssertTrue(text.contains("16") && text.contains("2026") && !text.contains("2026-06"), text)
        XCTAssertTrue(DayFormat.monthYear("2025-09-04")!.contains("2025"))
        XCTAssertNil(DayFormat.text(nil))
        XCTAssertEqual(DayFormat.text("soon"), "soon", "a value that isn't a date is shown as it is")
        XCTAssertNil(DayFormat.date("2026-13-01"))
        let boston = CLLocation(latitude: 42.3601, longitude: -71.0589), boise = CLLocation(latitude: 43.6158, longitude: -116.2030)
        let mi = Int((boston.distance(from: boise) / 1609.344).rounded())
        XCTAssertEqual(boston.milesText(to: boise), mi.formatted() + " mi", "miles are grouped for the reader's locale (\u{201C}2,285 mi\u{201D})")
        XCTAssertEqual(boise.milesText(to: boise), 0.0.formatted(.number.precision(.fractionLength(1))) + " mi")
    }

    /// The in-state test uses Idaho's outline, not its bounding box: Pullman and Jackson are inside the box.
    func testOutsideIdaho() {
        func inside(_ la: Double, _ lo: Double) -> Bool { LocationService.inIdaho(CLLocationCoordinate2D(latitude: la, longitude: lo)) }
        XCTAssertTrue(inside(43.6158, -116.2030), "Boise")
        XCTAssertTrue(inside(48.69, -116.32), "Bonners Ferry")
        XCTAssertTrue(inside(43.72, -111.11), "Driggs")
        XCTAssertTrue(inside(42.10, -111.88), "Preston")
        XCTAssertFalse(inside(46.73, -117.18), "Pullman, Washington")
        XCTAssertFalse(inside(47.66, -117.43), "Spokane")
        XCTAssertFalse(inside(43.48, -110.76), "Jackson, Wyoming")
        XCTAssertFalse(inside(37.33, -122.01), "Cupertino, where App Review usually is")
    }

    /// "Serves alcohol" names the license, says when only a store license matched, and never reads as "no".
    func testServesAlcohol() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.place(id: "a")!.servesAlcohol, "Yes · Liquor by the drink")
        XCTAssertEqual(m.place(id: "j")!.servesAlcohol, "Yes · Brewery", "a brewery's taproom serves on site")
        XCTAssertEqual(m.place(id: "k")!.servesAlcohol, "Beer or wine to go only (store license)")
        XCTAssertEqual(m.place(id: "d")!.servesAlcohol, "Unknown (no on-premises alcohol license matched)")
        XCTAssertFalse(m.places.contains { $0.servesAlcohol.hasPrefix("—") })
    }

    func testHonorsAreFactsWithTheirOwnLabels() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.place(id: "g")!.jamesBeardLabel, "America's Classic")
        XCTAssertEqual(m.place(id: "i")!.jamesBeardLabel, "James Beard winner")
        XCTAssertTrue(m.place(id: "i")!.isHonored)
        XCTAssertFalse(m.place(id: "b")!.hasHonors, "a hand-checked place isn't an honoree")
        XCTAssertNil(m.place(id: "d")!.liquor, "no license matched means unknown, never \u{201C}no\u{201D}")
    }

    func testNearestSort() async throws {
        let m = try await sampleModel()
        let boise = CLLocation(latitude: 43.6158, longitude: -116.2030)
        let near = m.list(.nearMe, sort: .nearest, search: "", here: boise)
        XCTAssertEqual(near.first?.id, "a", "the Grove Street place is closest to 8th and Main")
        let ids = near.map(\.id)
        XCTAssertLessThan(ids.firstIndex(of: "g")!, ids.firstIndex(of: "f")!, "Ketchum comes before Sandpoint")
    }

    func testSearchWordStartsTownsGuidesAndDishes() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> [String] { m.list(.all, sort: .name, search: q, here: nil).map(\.id) }
        XCTAssertEqual(ids("grove"), ["a"])
        XCTAssertTrue(ids("rove").isEmpty, "matches the start of words only")
        XCTAssertEqual(ids("coeur d alene"), ["j"], "Coeur d'Alene without the apostrophe")
        XCTAssertEqual(ids("coeur d'alene"), ["j"])
        XCTAssertEqual(ids("cda"), ["j"], "CDA, the local short form")
        XCTAssertEqual(ids("finger steaks"), ["b", "d"], "the guide's place, and a place named that way")
        XCTAssertEqual(ids("nampa finger steaks"), ["d"], "a town in the query narrows to it")
        XCTAssertEqual(ids("fry sauce"), ["b"], "a hand-checked dish is searchable")
        XCTAssertNil(Search.parse("fry sauce", towns: [:]).tag, "\u{201C}fry sauce\u{201D} is a dish, not a whole guide")
        XCTAssertEqual(ids("huckleberries"), ["f"], "plural to singular: the huckleberry guide")
        XCTAssertEqual(ids("west state street"), ["b"], "west/street match the abbreviated address")
        XCTAssertEqual(ids("blaine county"), ["g"], "the county is searchable")
        XCTAssertEqual(ids("🍕"), [], "nothing searchable typed means no results, not everything")
        XCTAssertEqual(ids("!!! ?"), [])
    }

    func testFiltersSavedPlacesAndMatchRates() async throws {
        let m = try await sampleModel()
        m.filters.hideChains = true
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Dutch Bros" })
        m.filters = Filters(confirmedOnly: true)
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.id == "d" }, "single listings drop out")
        m.filters = Filters(town: "Boise")
        XCTAssertEqual(Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id)), ["a", "b"])
        m.filters = Filters()
        let p = m.place(id: "b")!
        m.toggleSaved(p)
        XCTAssertEqual(m.savedPlaces.map(\.id), ["b"])
        m.toggleSaved(p)
        XCTAssertTrue(m.savedPlaces.isEmpty)
        XCTAssertEqual(m.matchRate(for: m.place(id: "b")!), "76%", "Colorado's Denver test of the same map data")
        XCTAssertNil(m.matchRate(for: m.place(id: "a")!), "places on an official record don't cite a listing rate")
        XCTAssertEqual(m.place(id: "a")!.tier, .licensed)
    }

    func testListCacheFollowsFiltersSearchAndLocation() async throws {
        let m = try await sampleModel()
        let all = m.list(.all, sort: .name, search: "", here: nil)
        XCTAssertTrue(all.contains { $0.name == "Dutch Bros" })
        m.filters.hideChains = true
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Dutch Bros" }, "a filter change isn't served from the cache")
        m.filters = Filters()
        XCTAssertEqual(m.list(.all, sort: .name, search: "", here: nil).map(\.id), all.map(\.id))
        XCTAssertEqual(m.list(.all, sort: .name, search: "grove", here: nil).map(\.id), ["a"])
        XCTAssertEqual(m.list(.all, sort: .name, search: "", here: nil).map(\.id), all.map(\.id))
        let boise = CLLocation(latitude: 43.6158, longitude: -116.2030), ketchum = CLLocation(latitude: 43.68, longitude: -114.36)
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: boise).first?.id, "a")
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: ketchum).first?.id, "g", "a new location isn't served from the cache")
    }

    func testNearMeIsntASearchWord() {
        let q = Search.parse("basque near me", towns: ["meridian": "Meridian"])
        XCTAssertEqual(q.tag, .basque)
        XCTAssertNil(q.town)
        XCTAssertTrue(q.tokens.isEmpty, "\"me\" mustn't match Meridian or Mexican places")
    }

    /// The one-pass normalize must agree with the regex version it replaced, on tricky strings and every bundled name and address.
    func testNormalizeMatchesTheRegexVersion() async throws {
        func reference(_ s: String) -> String {
            var t = s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .init(identifier: "en_US")).lowercased()
            t = t.replacingOccurrences(of: #"\b([a-z0-9])\s*&\s*([a-z0-9])\b"#, with: "$1$2", options: .regularExpression)
            t = t.replacingOccurrences(of: "&", with: " and ")
            t = t.replacingOccurrences(of: #"['’`]"#, with: "", options: .regularExpression)
            t = t.replacingOccurrences(of: #"[^\p{L}\p{N}]+"#, with: " ", options: .regularExpression)
            return t.trimmingCharacters(in: .whitespaces)
        }
        for s in ["Big Jud's", "B&B Cafe", "Rock & Roll Café", "  Phở 88!! ", "Jud’s", "Joe`s", "A&W", "½ Price", "/pôr/ Wine House",
                  "#vybe", "Coeur d'Alene", "1600 W State St #100", "🍕 Pizza", "Ⅻ Club", "Taquería", "", "---"] {
            XCTAssertEqual(Search.normalize(s), reference(s), s)
        }
        let m = AppModel(defaults: UserDefaults(suiteName: "norm-\(UUID().uuidString)")!)
        await m.load()
        for p in m.places {
            XCTAssertEqual(Search.normalize(p.name), reference(p.name), p.name)
            XCTAssertEqual(Search.normalize(p.fullAddress), reference(p.fullAddress), p.fullAddress)
        }
    }

    /// The real bundled file decodes and holds the guides the app promises.
    func testBundledData() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "bundle-\(UUID().uuidString)")!)
        await m.load()
        XCTAssertTrue(m.isLoaded, m.loadError ?? "")
        XCTAssertGreaterThan(m.restaurantCount, 3_500)
        XCTAssertGreaterThanOrEqual(m.count(.honors), 8)
        for g in HomeView.cards where g.isIdaho {
            XCTAssertTrue(m.places.filter(g.includes).allSatisfy(\.handChecked), "\(g.title) lists only hand-checked places")
        }
        XCTAssertEqual(Set(m.places.map(\.id)).count, m.places.count, "ids are unique")
        XCTAssertTrue(m.places.contains { $0.name == "Amano" && $0.city == "Caldwell" && $0.jamesBeardLabel == "James Beard winner" })
        XCTAssertTrue(m.places.contains { $0.name.caseInsensitiveCompare("The Pioneer Saloon") == .orderedSame && $0.jamesBeardLabel == "America's Classic" })
        // the screenshot script opens these by name
        for n in ScreenshotMode.savedNames + [ScreenshotMode.detailName] {
            XCTAssertTrue(m.places.contains { $0.name.caseInsensitiveCompare(n) == .orderedSame }, "screenshot place \(n) is in the data")
        }
        // no Google-derived data and no inspection results: the data file has none of these fields at all
        let raw = try String(contentsOf: Bundle.main.url(forResource: "places", withExtension: "json")!, encoding: .utf8)
        for key in ["\"rating\"", "\"reviews\"", "\"price\"", "\"gmap_id\"", "\"google21_open\"", "\"in\":"] {
            XCTAssertFalse(raw.contains(key), "\(key) must not ship")
        }
    }

    /// The bundled data against the data-hygiene findings of earlier states: adult clubs, directory and news links, mangled towns
    /// and names, lapsed-looking license dates, non-restaurants and places outside the state line.
    func testBundledDataGuards() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "guards-\(UUID().uuidString)")!)
        await m.load()
        XCTAssertTrue(m.isLoaded, m.loadError ?? "")
        XCTAssertEqual(DataGuards.adultVenues(m.places), [], "no place at a known strip club's address or under its name")
        XCTAssertEqual(DataGuards.badWebsites(m.places), [], "no directory, Google or news page as a restaurant's website")
        XCTAssertEqual(DataGuards.badTowns(m.places), [], "one spelling per town (Coeur d'Alene, McCall), none cut short")
        XCTAssertEqual(DataGuards.badNames(m.places), [], "no visible name ending in \u{201C} the\u{201D} or \u{201C} of\u{201D}, or just \u{201C}The\u{201D}")
        XCTAssertEqual(DataGuards.lapsedExpiries(m.places, listDate: m.liquorUpdated), [], "no license expiry before the list's own date")
        XCTAssertEqual(DataGuards.nonRestaurants(m.places), [], "no nail salon, senior home, gun store or gas station among the restaurants")
        XCTAssertEqual(DataGuards.outsideIdaho(m.places), [], "no Spokane, Pullman, Ontario or Jackson rows")
    }

    /// Each guard above fires on a copy of the bundled data broken the way QA found it elsewhere: a guard that can't fail guards
    /// nothing (Colorado's first website check had double backslashes in a raw string and matched nothing).
    func testGuardsCatchABrokenCopy() async throws {
        let raw = try Data(contentsOf: Bundle.main.url(forResource: "places", withExtension: "json")!)
        var file = try XCTUnwrap(JSONSerialization.jsonObject(with: raw) as? [String: Any])
        var places = try XCTUnwrap(file["places"] as? [[String: Any]])
        var cities = try XCTUnwrap(file["cities"] as? [String])
        cities.append("Coeur D Alene")
        // ordinary visible places, each broken one way
        let idx = places.indices.filter { places[$0]["v"] == nil }.prefix(8).map { $0 }
        places[idx[0]]["w"] = "https://www.yelp.com/biz/some-place"
        places[idx[1]]["w"] = "https://www.idahostatesman.com/news/local/article123.html"
        places[idx[2]]["a"] = "1500 West Grove Street"
        places[idx[2]]["c"] = try XCTUnwrap(cities.firstIndex(of: "Boise"))
        places[idx[3]]["c"] = cities.count - 1
        places[idx[4]]["n"] = "Kitchen the"
        places[idx[5]]["lic"] = [["src": "Idaho ABC license", "id": "0000", "type": "Liquor by the drink", "exp": "2014-05-16"]]
        places[idx[6]]["la"] = 47.6588
        places[idx[6]]["lo"] = -117.426
        places[idx[7]]["n"] = "Tipsy Nails & Spa"
        file["places"] = places
        file["cities"] = cities
        if file["liquor_updated"] == nil || file["liquor_updated"] is NSNull { file["liquor_updated"] = "2026-10-08" }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("places-broken.json")
        try JSONSerialization.data(withJSONObject: file).write(to: url)
        let m = AppModel(defaults: UserDefaults(suiteName: "broken-\(UUID().uuidString)")!)
        await m.load(from: url)
        XCTAssertTrue(m.isLoaded, m.loadError ?? "")
        let id = idx.map { places[$0]["id"] as? String }
        func caught(_ found: [String], _ i: Int, _ what: String) {
            XCTAssertTrue(found.contains { $0.contains("[\(id[i] ?? "?")]") }, "the guard missed \(what)")
        }
        caught(DataGuards.badWebsites(m.places), 0, "a Yelp page")
        caught(DataGuards.badWebsites(m.places), 1, "an Idaho Statesman story")
        caught(DataGuards.adultVenues(m.places), 2, "1500 West Grove Street (= 1500 W Grove St)")
        XCTAssertTrue(DataGuards.badTowns(m.places).contains("Coeur D Alene"), "the guard missed \u{201C}Coeur D Alene\u{201D}")
        caught(DataGuards.badNames(m.places), 4, "\u{201C}Kitchen the\u{201D}")
        caught(DataGuards.lapsedExpiries(m.places, listDate: m.liquorUpdated), 5, "a 2014 expiry")
        caught(DataGuards.outsideIdaho(m.places), 6, "a place in Spokane")
        caught(DataGuards.nonRestaurants(m.places), 7, "a nail salon shown as a restaurant")
    }
}

/// Checks on the bundled data, written as functions so testGuardsCatchABrokenCopy can prove each one fires.
enum DataGuards {
    /// directories, Google and news sites: matched on the link's host, so "smart.com" isn't "rt.com"
    static let badHosts = #"^https?://([^/?#]*\.)?(yelp\.com|business\.site|google\.com|groupon\.com|yellowpages\.com|idahostatesman\.com|boisedev\.com|idahopress\.com|spokesman\.com|rt\.com)([:/?#]|$)"#

    static func badWebsites(_ places: [Place]) -> [String] {
        places.compactMap { p in
            guard let w = p.website?.absoluteString, w.range(of: badHosts, options: [.regularExpression, .caseInsensitive]) != nil else { return nil }
            return "\(p.name) [\(p.id)]: \(w)"
        }
    }

    /// Adult venues Overture lists in Idaho (data/research/adult_venues.json), by street address in their town, and by name.
    static let adultAddresses: [(address: String, town: String)] = [
        ("1826 W Main St", "Boise"), ("610 S Vista Ave", "Boise"), ("1500 W Grove St", "Boise"), ("4348 W State St", "Boise"),
        ("5781 W Overland Rd", "Boise"), ("6717 W Seltice Way", "Post Falls"), ("6727 W Seltice Way", "Post Falls"),
        ("1259 Yellowstone Ave", "Pocatello"),
    ]
    static let adultNames = #"spearmint rhino|satin dolls|showgirls|torch lounge|\btorch 2\b|gentlem[ae]n['’]?s club|strip club|exotic dancer|cabaret"#

    static func adultVenues(_ places: [Place]) -> [String] {
        // "1500 West Grove Street" and "1500 W Grove St" are the same address: street words abbreviated, case and punctuation gone
        let wanted = adultAddresses.map { (Search.normalizeAddress($0.address), $0.town) }
        return places.compactMap { p in
            let a = Search.normalizeAddress(p.address ?? "")
            let atAddress = !a.isEmpty && wanted.contains { $0.0 == a && $0.1 == p.city }
            let named = p.name.range(of: adultNames, options: [.regularExpression, .caseInsensitive]) != nil
            return atAddress || named ? "\(p.name) [\(p.id)], \(p.address ?? "")" : nil
        }
    }

    /// one spelling per town (the listings write Coeur d'Alene four ways), and every town at least three letters
    static func badTowns(_ places: [Place]) -> [String] {
        let variants: Set = ["Coeur D Alene", "Coeur D'Alene", "Coeur d Alene", "Mccall", "Mc Call", "St Maries", "St Anthony", "Idaho-Falls"]
        return Set(places.compactMap(\.city)).filter { t in variants.contains(t) || t.filter(\.isLetter).count < 3 }.sorted()
    }

    /// a name cut off after "the" or "of" ("Kitchen the", "Wines of") or nothing but "The", among the places shown by default
    static func badNames(_ places: [Place]) -> [String] {
        places.filter { p in
            let n = p.name.trimmingCharacters(in: .whitespaces).lowercased()
            return !p.isVenue && (n.hasSuffix(" the") || n.hasSuffix(" of") || n == "the")
        }.map { "\($0.name) [\($0.id)]" }
    }

    /// a license expiry before the active list's own date reads as lapsed (renewals pending stay on the list)
    static func lapsedExpiries(_ places: [Place], listDate: String?) -> [String] {
        places.flatMap { p in
            p.licenses.compactMap { l in l.exp.flatMap { e in listDate.map { e < $0 } ?? true ? "\(p.name) [\(p.id)]: \(l.id) \(e)" : nil } }
        }
    }

    /// businesses that hold a beer-and-wine license but aren't places to eat (Colorado's QA: nail bars, senior homes, a gun store,
    /// gas stations), among the places shown by default
    static let nonRestaurantNames = #"\bnails?\b|\bsenior\b|assisted living|firearms|gun (?:shop|store|range)|petroleum|\bsinclair\b"#

    static func nonRestaurants(_ places: [Place]) -> [String] {
        places.filter { !$0.isVenue && $0.name.range(of: nonRestaurantNames, options: [.regularExpression, .caseInsensitive]) != nil }
            .map { "\($0.name) [\($0.id)]" }
    }

    /// every place inside the state line: border-town listings (Spokane, Pullman, Ontario, Jackson) mustn't ship
    static func outsideIdaho(_ places: [Place]) -> [String] {
        places.filter { p in p.coordinate.map { !LocationService.inIdaho($0) } ?? false }.map { "\($0.name) [\($0.id)], \($0.city ?? "")" }
    }
}
