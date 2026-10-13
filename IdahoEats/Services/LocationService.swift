import CoreLocation
import Observation
import UIKit

/// "Near me" sorting. Asks for when-in-use permission only when a list is sorted by distance or "My location" is tapped; the location never leaves the device.
@MainActor
@Observable
final class LocationService: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private(set) var location: CLLocation?
    private(set) var status: CLAuthorizationStatus = .notDetermined
    /// no fix within 12 seconds, or Core Location reported an error
    private(set) var failed = false
    private var timeout: Task<Void, Never>?
    /// when the current request started: a fix from before it is a cached one (from launch, or before a drive) and doesn't count
    private var askedAt = Date.distantPast

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        status = manager.authorizationStatus
    }

    var isDenied: Bool { status == .denied || status == .restricted }

    /// Every place is in Idaho, so a reader elsewhere (an App Reviewer in California, say) gets told rather than an empty map.
    var isOutsideIdaho: Bool {
        guard let c = location?.coordinate else { return false }
        return !Self.inIdaho(c)
    }

    /// Idaho's outline, simplified (about 4 km) and padded 3 km from the Overture state shape: a box would take in Pullman and
    /// Jackson. (latitude, longitude) pairs.
    nonisolated static let outline: [(Double, Double)] = [
        (44.426, -117.25), (44.746, -117.085), (44.901, -116.88), (45.036, -116.875), (45.61, -116.501), (45.726, -116.567),
        (45.798, -116.795), (45.888, -116.883), (46.077, -117.011), (46.232, -116.987), (46.346, -117.092), (49.008, -117.061),
        (49.03, -116.041), (48.0, -116.019), (47.713, -115.698), (47.558, -115.684), (47.486, -115.6), (47.427, -115.643),
        (47.32, -115.495), (47.281, -115.302), (46.744, -114.735), (46.759, -114.635), (46.668, -114.588), (46.66, -114.294),
        (46.137, -114.456), (45.877, -114.359), (45.783, -114.515), (45.704, -114.465), (45.597, -114.509), (45.495, -114.33),
        (45.736, -113.991), (45.63, -113.794), (45.342, -113.702), (45.072, -113.425), (44.889, -113.43), (44.795, -113.111),
        (44.471, -112.976), (44.434, -112.901), (44.534, -112.721), (44.485, -112.394), (44.598, -112.29), (44.557, -112.107),
        (44.596, -111.866), (44.549, -111.82), (44.586, -111.555), (44.725, -111.512), (44.785, -111.386), (44.493, -111.028),
        (41.99, -111.019), (41.972, -117.036), (43.831, -117.063), (44.017, -116.971), (44.095, -117.006), (44.158, -116.934),
        (44.266, -117.237)]

    /// Ray casting against the outline.
    nonisolated static func inIdaho(_ c: CLLocationCoordinate2D) -> Bool {
        var inside = false
        var j = outline.count - 1
        for i in outline.indices {
            let (yi, xi) = outline[i], (yj, xj) = outline[j]
            if (yi > c.latitude) != (yj > c.latitude), c.longitude < (xj - xi) * (c.latitude - yi) / (yj - yi) + xi { inside.toggle() }
            j = i
        }
        return inside
    }

    /// Once location is off for the app, iOS won't ask again; the app's page in Settings is the only way back.
    static func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
    }

    func request() {
        switch manager.authorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways: locate()
        default: break
        }
    }

    private func locate() {
        failed = false
        let asked = Date()
        askedAt = asked
        manager.requestLocation()
        timeout?.cancel()
        timeout = Task { [weak self] in
            try? await Task.sleep(for: .seconds(12))
            guard let self, !Task.isCancelled else { return }
            if (self.location?.timestamp ?? .distantPast) < asked { self.failed = true }
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        let s = m.authorizationStatus
        Task { @MainActor in
            self.status = s
            if s == .authorizedWhenInUse || s == .authorizedAlways { self.locate() }
        }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let l = locations.last else { return }
        Task { @MainActor in
            // "My location" needs a fresh fix on every tap: a cached one from before the request would put you back where you were
            guard l.timestamp >= self.askedAt.addingTimeInterval(-2) else { return }
            self.location = l; self.failed = false; self.timeout?.cancel()
        }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in if self.location == nil { self.failed = true } }
    }
}

extension CLLocation {
    /// "0.4 mi", "12 mi", "1,012 mi" (an App Reviewer in California is a thousand miles out)
    func milesText(to other: CLLocation) -> String {
        let mi = distance(from: other) / 1609.344
        return (mi < 10 ? mi.formatted(.number.precision(.fractionLength(1))) : Int(mi.rounded()).formatted()) + " mi"
    }
}
