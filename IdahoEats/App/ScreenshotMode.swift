import Foundation
import CoreLocation
import UIKit

/// `-screenshot <name>` opens one screen with fixed state for App Store screenshots (scripts/capture-screenshots.sh).
/// Names: home, basque, fingersteaks, huckleberry, detail, map, honors, oldest, saved, about.
enum ScreenshotMode {
    /// Debug builds only: an App Store build ignores the launch argument, so no one can reach seeded screens or fake locations.
    static var name: String? {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screenshot"), i + 1 < args.count else { return nil }
        return args[i + 1]
        #else
        return nil
        #endif
    }
    static var isActive: Bool { name != nil }

    /// hand-checked places with a clean, current source (no App Store image shows anything negative)
    static let savedNames = ["Bar Gernika", "The Pioneer Saloon", "Westside Drive-In", "Amano"]
    static let detailName = "The Pioneer Saloon"

    @MainActor
    static func apply(to model: AppModel) {
        guard let name, model.isLoaded else { return }
        model.filters = Filters()
        // downtown Boise (8th and Main), so "nearest" lists have distances without a permission prompt
        model.screenshotLocation = CLLocation(latitude: 43.6158, longitude: -116.2030)
        // by name, ignoring case: a rebuild that takes the research spelling still finds the place
        let pick = { (n: String) in model.places.first { $0.name.caseInsensitiveCompare(n) == .orderedSame } }
        for n in Self.savedNames {
            if let p = pick(n), !model.isSaved(p) { model.toggleSaved(p) }
        }
        let open = { (g: Guide) in model.tab = .guides; model.selectedGuide = g; model.guidesPath = [.guide(g)] }
        switch name {
        case "basque": open(.basque)
        case "fingersteaks": open(.fingerSteaks)
        case "huckleberry": open(.huckleberry)
        case "honors": open(.honors)
        case "oldest": open(.oldest)
        case "detail":
            open(.oldest)
            if let p = pick(Self.detailName) ?? model.places.first { model.selectedPlace = p; model.guidesPath.append(.place(p)) }
        case "map": model.tab = .map
        case "saved": model.tab = .saved
        case "about": model.tab = .about
        default: model.tab = .guides; model.selectedGuide = nil
        }
        // iPad shows the place column next to every list, so give each shot a place instead of "Pick a place".
        guard UIDevice.current.userInterfaceIdiom == .pad, model.selectedPlace == nil else { return }
        let place: Place? = switch name {
        case "basque": model.list(.basque, sort: .featured, search: "", here: nil).first
        case "fingersteaks": model.list(.fingerSteaks, sort: .featured, search: "", here: nil).first
        case "huckleberry": model.list(.huckleberry, sort: .featured, search: "", here: nil).first
        case "honors": model.list(.honors, sort: .iconic, search: "", here: nil).first
        case "saved": pick(Self.savedNames[0])
        case "about": nil
        default: pick(Self.detailName)
        }
        model.selectedPlace = place
    }
}
