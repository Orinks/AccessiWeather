import SwiftUI

@main
struct AccessiWeatherApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
                .environmentObject(model.settings)
                .environmentObject(model.locationStore)
        }
    }
}
