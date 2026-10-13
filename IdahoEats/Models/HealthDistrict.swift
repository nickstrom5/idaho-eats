import Foundation

/// Idaho's seven public health districts license and inspect restaurants. None publishes results in bulk, so a place's detail points
/// to its district's own lookup. Every URL was fetched on 2026-10-08 and renders (South Central's portal itself keeps automated
/// agents out, so the app links to the district's inspections page, which links to it).
struct HealthDistrict: Hashable {
    let name: String
    let lookup: URL?

    static let all: [String: HealthDistrict] = {
        let d: [(String, String?, [String])] = [
            ("Panhandle Health District", "https://panhandlehealthdistrict.org/licensing-and-permitting/food-establishments/",
             ["Benewah", "Bonner", "Boundary", "Kootenai", "Shoshone"]),
            ("Public Health – Idaho North Central District", "https://id.healthinspections.us/idaho/food/",
             ["Clearwater", "Idaho", "Latah", "Lewis", "Nez Perce"]),
            ("Southwest District Health", nil, ["Adams", "Canyon", "Gem", "Owyhee", "Payette", "Washington"]),
            ("Central District Health", "https://cdh.idaho.gov/licenses-permits-inspections/food-establishments/", ["Ada", "Boise", "Elmore", "Valley"]),
            ("South Central Public Health District", "https://phd5.idaho.gov/inspections/",
             ["Blaine", "Camas", "Cassia", "Gooding", "Jerome", "Lincoln", "Minidoka", "Twin Falls"]),
            ("Southeastern Idaho Public Health", "https://inspectionsonline.us/foodsafety/idbannockpocatello/search.htm",
             ["Bannock", "Bear Lake", "Bingham", "Butte", "Caribou", "Franklin", "Oneida", "Power"]),
            ("Eastern Idaho Public Health", "https://inspectionsonline.us/foodsafety/idbonnevilleidahofalls/search.htm",
             ["Bonneville", "Clark", "Custer", "Fremont", "Jefferson", "Lemhi", "Madison", "Teton"]),
        ]
        var out: [String: HealthDistrict] = [:]
        for (name, url, counties) in d {
            for c in counties { out[c + " County"] = HealthDistrict(name: name, lookup: url.flatMap(URL.init(string:))) }
        }
        return out
    }()

    static func of(county: String?) -> HealthDistrict? { county.flatMap { all[$0] } }
}
