import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        TabView {
            WeatherView()
                .tabItem { Label("Weather", systemImage: "cloud.sun") }
            AlertsView()
                .tabItem { Label("Alerts", systemImage: "exclamationmark.triangle") }
                .badge(model.report?.alerts.count ?? 0)
            LocationsView()
                .tabItem { Label("Locations", systemImage: "mappin.and.ellipse") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gear") }
        }
        .task {
            await model.refresh(announce: false)
        }
    }
}
