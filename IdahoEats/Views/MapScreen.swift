import SwiftUI
import MapKit

struct MapScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    var selection: Binding<Place?>? = nil

    @State private var layer: Layer = .picks
    @State private var pushed: Place?
    @State private var region: MKCoordinateRegion?
    /// "My location": where to move the map (a new object each tap, so a second tap re-centers after panning away)
    @State private var centerOn: CLLocation?
    @State private var centerWhenFound = false
    @State private var notice: String?
    @State private var askSettings = false

    /// 16,000+ restaurants at once kept Wisconsin's map busy for a minute and more in QA, so the Everything layer fills in
    /// only once you zoom to about town size (this many degrees of latitude on screen), and only for what's in view.
    private static let everythingSpan = 0.3
    /// Even town size can be thousands of places (Colorado's QA counted 5,900 pins in Denver: the map pegged the CPU and grew to
    /// 358 MB), so the Everything layer shows at most this many: the honored places and Idaho picks first, then the nearest.
    static let pinCap = 600

    /// The map's narrower side, in degrees of latitude. MapKit stretches the other side to fit the view, so a tall, narrow iPad column
    /// zoomed to a town shows 0.3°+ of latitude; judging by the narrower side keeps "town size" the same on every screen shape.
    static func townSpan(_ r: MKCoordinateRegion) -> Double {
        min(r.span.latitudeDelta, r.span.longitudeDelta * cos(r.center.latitude * .pi / 180))
    }

    enum Layer: String, CaseIterable, Identifiable {
        case picks = "Idaho picks", fingerSteaks = "Finger steaks", basque = "Basque", honors = "Honors", all = "Everything"
        var id: String { rawValue }
        /// Idaho picks: every hand-checked place in one of the Idaho guides
        func includes(_ p: Place) -> Bool {
            switch self {
            case .picks: p.isClassic
            case .fingerSteaks: Guide.fingerSteaks.includes(p)
            case .basque: Guide.basque.includes(p)
            case .honors: Guide.honors.includes(p)
            case .all: true
            }
        }
    }

    var body: some View {
        let layerPlaces = model.places.filter { layer.includes($0) && model.filters.allows($0) && $0.coordinate != nil }
        let zoomedOut = layer == .all && (region.map(Self.townSpan) ?? .infinity) > Self.everythingSpan
        let nearby = layer != .all || zoomedOut ? [] : layerPlaces.filter(inView)
        let places = layer != .all ? layerPlaces : Self.capped(nearby, around: region?.center)
        ZStack(alignment: .top) {
            ClusteredMap(places: places, showsUser: location.location != nil, center: centerOn, centerSpan: ScreenshotMode.name == "map" ? 0.006 : 0.15,
                         onRegion: { region = $0 }) { p in
                if let selection { selection.wrappedValue = p } else { pushed = p }
            }
            .ignoresSafeArea(edges: .bottom)
            VStack(spacing: 6) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(Layer.allCases) { l in
                            Button { layer = l } label: {
                                Text(l.rawValue).font(.subheadline.weight(.semibold))
                                    .padding(.horizontal, 12).padding(.vertical, 8)
                                    .foregroundStyle(layer == l ? .white : Theme.green)
                                    .background(Capsule().fill(layer == l ? Theme.green : Theme.surface))
                                    .overlay(Capsule().strokeBorder(Theme.rule2, lineWidth: layer == l ? 0 : 1))
                            }
                            .accessibilityAddTraits(layer == l ? .isSelected : [])
                        }
                    }
                    .padding(.horizontal, 12)
                }
                Text(notice ?? (zoomedOut ? "Zoom in to a town to see all \(layerPlaces.count.formatted()) places"
                               : places.count < nearby.count ? "Zoom in to see all \(nearby.count.formatted()) places here"
                               : "\(places.count.formatted()) \(layer == .all ? "places here" : "places") · tap a pin, then its name"))
                    .font(.caption).foregroundStyle(Theme.ink2)
                    .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(.thinMaterial))
            }
            .padding(.top, 8)
        }
        .inlineTitle("Map")
        .navigationDestination(item: $pushed) { PlaceDetailView(place: $0) }
        // iPhone-size: the open place is also the model's, so an iPad layout opens on it; and the reverse after an iPad layout
        .onChange(of: pushed) { _, p in if let p { model.selectedPlace = p } }
        .onChange(of: model.handoffPlace, initial: true) { _, p in
            guard selection == nil, model.tab == .map, let p else { return }
            model.handoffPlace = nil
            pushed = p
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    if location.isDenied {
                        askSettings = true
                    } else {
                        // a fix from launch may be miles out of date, so always ask for a fresh one; a very recent fix moves the map now
                        if let here = location.location, here.timestamp.timeIntervalSinceNow > -60 { center(on: here) }
                        centerWhenFound = true
                        location.request()
                    }
                } label: { Label("My location", systemImage: "location") }
            }
        }
        .onAppear {
            // App Store screenshot: the Idaho picks on Boise's Basque Block, zoomed in so individual pins show rather than cluster bubbles
            // (DEBUG builds only, see ScreenshotMode)
            if ScreenshotMode.name == "map", centerOn == nil { centerOn = CLLocation(latitude: 43.6136, longitude: -116.2030) }   // the Basque Block
        }
        .onChange(of: location.location) { _, here in
            guard centerWhenFound, let here else { return }
            centerWhenFound = false
            center(on: here)
        }
        .onChange(of: location.failed) { _, failed in
            guard failed && centerWhenFound else { return }
            centerWhenFound = false
            // the map already moved to a fix from the last minute or so; only say so when there was nothing to go on
            if (location.location?.timestamp.timeIntervalSinceNow ?? -.infinity) < -90 {
                flash("Couldn't find your location. Check that Location Services is on.")
            }
        }
        .alert("Location is off", isPresented: $askSettings) {
            Button("Open Settings") { LocationService.openSettings() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Turn on location for Idaho Eats in Settings to center the map on you. It stays on your device.")
        }
    }
}

extension MapScreen {
    /// Town-level zoom on the reader, unless they're outside Idaho: then the map stays on the state and says why.
    private func center(on here: CLLocation) {
        if location.isOutsideIdaho {
            flash("You're outside Idaho, so the map stays on the state.")
        } else {
            centerOn = CLLocation(latitude: here.coordinate.latitude, longitude: here.coordinate.longitude)
        }
    }

    private func flash(_ text: String) {
        notice = text
        Task { try? await Task.sleep(for: .seconds(5)); if notice == text { notice = nil } }
    }

    /// On screen, with a quarter screen of margin on each side so a small pan doesn't show empty edges.
    private func inView(_ p: Place) -> Bool {
        guard let r = region, let c = p.coordinate else { return false }
        return abs(c.latitude - r.center.latitude) <= 0.75 * r.span.latitudeDelta && abs(c.longitude - r.center.longitude) <= 0.75 * r.span.longitudeDelta
    }

    /// At most `pinCap` pins: the honored places and Idaho picks first (the ones with priority pins), then the nearest to the center.
    static func capped(_ places: [Place], around center: CLLocationCoordinate2D?, limit: Int = pinCap) -> [Place] {
        guard places.count > limit, let center else { return places }
        let k = cos(center.latitude * .pi / 180)
        func d2(_ p: Place) -> Double {
            guard let c = p.coordinate else { return .greatestFiniteMagnitude }
            let dy = c.latitude - center.latitude, dx = (c.longitude - center.longitude) * k
            return dy * dy + dx * dx
        }
        return places.map { ($0, $0.isHonored || $0.isClassic, d2($0)) }
            .sorted { $0.1 != $1.1 ? $0.1 : $0.2 < $1.2 }
            .prefix(limit).map(\.0)
    }
}

/// MKMapView with clustering: SwiftUI's Map can't cluster thousands of pins.
struct ClusteredMap: UIViewRepresentable {
    let places: [Place]
    let showsUser: Bool
    /// move the map here (town-level zoom) whenever a new location object arrives
    var center: CLLocation? = nil
    /// degrees of latitude and longitude shown around `center`
    var centerSpan: Double = 0.15
    var onRegion: (MKCoordinateRegion) -> Void = { _ in }
    let onSelect: (Place) -> Void

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.pointOfInterestFilter = .excludingAll
        map.register(PlaceMarker.self, forAnnotationViewWithReuseIdentifier: PlaceMarker.id)
        map.register(ClusterMarker.self, forAnnotationViewWithReuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier)
        // all of Idaho, from the Nevada line to Canada
        map.setRegion(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 45.5, longitude: -114.15),
                                         span: MKCoordinateSpan(latitudeDelta: 7.6, longitudeDelta: 6.6)), animated: false)
        let start = map.region
        DispatchQueue.main.async { onRegion(start) }
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onRegion = onRegion
        map.showsUserLocation = showsUser
        if let c = center, c !== context.coordinator.centered {
            context.coordinator.centered = c
            map.setRegion(MKCoordinateRegion(center: c.coordinate, span: MKCoordinateSpan(latitudeDelta: centerSpan, longitudeDelta: centerSpan)), animated: true)
        }
        let want = Set(places.map(\.id))
        let have = map.annotations.compactMap { $0 as? PlaceAnnotation }
        let haveIds = Set(have.map(\.place.id))
        guard want != haveIds else { return }
        map.removeAnnotations(have.filter { !want.contains($0.place.id) })
        map.addAnnotations(places.filter { !haveIds.contains($0.id) }.map(PlaceAnnotation.init))
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var onSelect: ((Place) -> Void)?
        var onRegion: ((MKCoordinateRegion) -> Void)?
        var centered: CLLocation?

        func mapView(_ map: MKMapView, regionDidChangeAnimated animated: Bool) {
            let r = map.region
            DispatchQueue.main.async { self.onRegion?(r) }   // not during a SwiftUI view update
        }

        func mapView(_ map: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation { return nil }
            if annotation is MKClusterAnnotation { return nil }   // the registered ClusterMarker
            return map.dequeueReusableAnnotationView(withIdentifier: PlaceMarker.id, for: annotation)
        }

        func mapView(_ map: MKMapView, annotationView view: MKAnnotationView, calloutAccessoryControlTapped control: UIControl) {
            if let a = view.annotation as? PlaceAnnotation { onSelect?(a.place) }
        }

        func mapView(_ map: MKMapView, didSelect annotation: MKAnnotation) {
            if let cluster = annotation as? MKClusterAnnotation {
                map.showAnnotations(cluster.memberAnnotations, animated: true)
                map.deselectAnnotation(cluster, animated: false)
            }
        }
    }
}

final class PlaceAnnotation: NSObject, MKAnnotation {
    let place: Place
    let coordinate: CLLocationCoordinate2D
    var title: String? { place.name }
    var subtitle: String? { place.townLine }
    init(_ p: Place) { place = p; coordinate = p.coordinate! }
}

final class PlaceMarker: MKMarkerAnnotationView {
    static let id = "place"
    override var annotation: MKAnnotation? { didSet { configure() } }

    private func configure() {
        clusteringIdentifier = "places"
        canShowCallout = true
        let info = UIButton(type: .detailDisclosure)
        info.accessibilityLabel = "Details"
        rightCalloutAccessoryView = info
        guard let p = (annotation as? PlaceAnnotation)?.place else { return }
        let classic = p.isClassic
        // James Beard places in pine with a rosette, hand-checked Idaho picks in russet with their guide's glyph, the rest huckleberry
        let beard = p.jamesBeard != nil
        markerTintColor = UIColor(beard ? Theme.pine : classic ? Theme.gold : Theme.green)
        glyphTintColor = UIColor(classic && !beard ? Theme.green : .white)
        let glyph = beard ? "rosette" : !classic ? "fork.knife"
            : p.tags.contains(.basque) ? "wineglass.fill" : p.tags.contains(.fingerSteaks) || p.tags.contains(.driveIn) ? "car.fill"
            : p.tags.contains(.huckleberry) ? "birthday.cake.fill" : p.tags.contains(.trout) ? "fish.fill"
            : p.tags.contains(.taqueria) ? "takeoutbag.and.cup.and.straw.fill" : p.tags.contains(.historic) ? "building.columns.fill" : "fork.knife"
        glyphImage = UIImage(systemName: glyph)
        displayPriority = p.isHonored || classic ? .defaultHigh : .defaultLow
    }
}

final class ClusterMarker: MKMarkerAnnotationView {
    override var annotation: MKAnnotation? {
        didSet {
            markerTintColor = UIColor(Theme.green)
            let n = (annotation as? MKClusterAnnotation)?.memberAnnotations.count ?? 0
            glyphText = "\(n)"
            // VoiceOver read a bare number
            isAccessibilityElement = true
            accessibilityLabel = "\(n.formatted()) places"
            accessibilityHint = "Zooms in to show them"
            displayPriority = .defaultHigh
        }
    }
}
