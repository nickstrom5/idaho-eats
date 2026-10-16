# App Review: answers prepared before the first submission

Wisconsin Eats got Guideline 2.1 "Information Needed" on 2026-10-05 (a new developer account has a limited review history): Apple
asked for a screen recording from a physical device, starting at launch, and answers to six questions. Idaho Eats should expect the
same, so the reply below goes into **App Review Information → Notes** from the first submission, and the recording is made before
submitting. If Apple asks anyway, paste the same reply into App Review → the submission → **Reply to App Review** and attach the recording.

## Screen recording (Nick, on his iPhone, latest iOS)

The app must be on the phone first, through TestFlight: an internal group with Nick in it. The tester email must be the Apple ID signed
in under Settings › your name › Media & Purchases on the phone; when it isn't, TestFlight shows "not available". Check that first.
Record with Control Center → Screen Recording, 60–120 seconds, no sound needed:

1. Start on the Home Screen and tap **Idaho Eats**. The recording must begin with the launch.
2. Home: scroll the guide cards a little.
3. Tap **Basque**, then tap **Bar Gernika** (or any place).
4. On the place: tap **Ratings, hours & photos**. Apple's place card opens. Close it.
5. Tap the **heart** (Save), then go back.
6. Back on Home, tap the search box and type `finger steaks`. Open a result.
7. Tap the **Map** tab, then tap **Finger steaks**, then a pin and its name.
8. Tap the **Saved** tab, where the saved place shows. Then tap **About** and scroll to the sources.

## Reply text (under 4,000 characters; numbers from playbook/site-numbers.json)

```
Thank you. Here is the information requested.

1. Screen recording from an iPhone on the latest iOS: attached, from launch. There is no account, login, user-generated or paid content.

2. Purpose and audience: Idaho Eats is a free guide to restaurants in Idaho. Its focus is the state's own food: Basque kitchens on Boise's Basque Block, finger steaks and drive-ins, spud plates, huckleberry, Idaho trout, taquerías and historic saloons, each place checked by hand in fall 2026 against a 2025 or 2026 source (the restaurant's own website or menu, or local news), plus Idaho's James Beard Foundation honorees, as facts. It also lists 4,023 restaurants, cafés, bars and bakeries statewide. It is for Idaho residents and visitors deciding where to eat. No ads, account or tracking.

3. How to use it (no login, no setup, no sample files needed):
- Home → any guide (Basque, Finger Steaks & Drive-Ins, Spud Plates, Huckleberry, Idaho Trout, Taquerías, Historic Saloons, James Beard Honors, Oldest Places, Near Me) → tap a place.
- On a place, tap "Ratings, hours & photos" to open Apple Maps' own place card through MapKit. Directions, Call and Website are below it.
- Search by name, town, street or dish ("finger steaks boise", "huckleberry").
- The Map tab shows the Idaho picks, Finger Steaks, Basque and Honors guides as pins, plus nearby restaurants once zoomed in to a town. "My location" and the Nearest sort use location only if allowed, on the device.
- The heart saves a place on the device, under the Saved tab. The About tab lists the data sources, licenses and the independence statement.
- On iPad, a sidebar replaces the tabs; a place opens in the right-hand column.
- Outside Idaho (as App Review usually is), the map says so and stays on Idaho.

4. External services and data:
- Apple MapKit: maps, local search to find a place's Apple Maps listing, and Apple's place card for live hours, photos and ratings.
- Core Location: optional, on-device only, for distance sorting.
- Core Spotlight: on-device indexing so places appear in iPhone search.
- No backend, accounts, analytics, advertising, payments or AI services. The restaurant data is bundled in the app.
- Bundled data: Overture Maps open data (CDLA Permissive 2.0 and Apache 2.0; license texts in the app); James Beard honors (facts only); and our own research of restaurants' websites, menus and local news.
- Privacy policy and support: a static site on GitHub Pages, https://nickstrom5.github.io/idaho-eats/

5. Regional differences: none. The content covers Idaho; the app works the same everywhere in the United States.

6. Regulated or protected material: the app is not in a regulated industry and includes no protected third-party material. The data is open-licensed or public, credited on the About tab. Ratings, hours and photos are shown only inside Apple's own place card through MapKit, under Apple's terms; the app stores no ratings or reviews. Idaho's health districts don't publish inspection results in bulk, so the app shows none and links each place's district lookup instead. Honors are stated as facts, with a trademark notice. Website links were checked before release (each must be the restaurant's own page), and strip clubs and other adult venues are excluded by name, address and category. The app is independent and not affiliated with any restaurant, agency or the James Beard Foundation.

Support: nick@eatsranked.com
```
When the ABC license list is in the data, add to point 4: "Idaho State Police Alcohol Beverage Control retail license records
(public records; licensee names not shown)".

## If App Review cites Guideline 4.3(a) (Resolution Center only; never in the Notes)

Nick's call (2026-10-07, STATE_EATS_PLAYBOOK.md): submit Idaho Eats as its own app and keep this answer ready. Don't volunteer a
comparison with the other state apps. If Apple still asks for one app, the fallback is a single multi-state app with a state picker
(Nick decides then). Numbers from `playbook/site-numbers.json`.

```
Thank you for the review. Idaho Eats is not a repackaged copy of another app. It is a guide built for Idaho, from Idaho's own sources:
- Its guides are Idaho's food traditions, each place checked by hand against a 2025 or 2026 source: Basque kitchens on Boise's Basque
  Block, finger steaks and drive-ins with fry sauce, spud plates, huckleberry shakes and pies from North Idaho, Magic Valley trout,
  taquerías and the state's historic saloons.
- Each place links the Idaho public health district that inspects it (Idaho's seven districts publish no inspection results in
  bulk, and the app says so), and Idaho's James Beard honorees are stated as facts.
- Its map and "outside Idaho" check use Idaho's own state and county outlines.
- None of its places, research, guides or text is shared with any other app; the people who use it are in Idaho or traveling there.
We're glad to answer any question about how the app works.
```

When the site moves to idaho.eatsranked.com, change the GitHub Pages line in point 4 to the new address. Keep the numbers in point 2
in step with `playbook/site-numbers.json`, and the reply under 4,000 characters (count it with Python).
