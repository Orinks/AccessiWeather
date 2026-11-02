import SwiftUI

enum AppTab: Hashable {
    case weather, alerts, locations, settings
}

struct ContentView: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject private var router = NotificationRouter.shared
    @State private var tab: AppTab = .weather

    var body: some View {
        TabView(selection: $tab) {
            WeatherView()
                .tabItem { Label("Weather", systemImage: "cloud.sun") }
                .tag(AppTab.weather)
            AlertsView()
                .tabItem { Label("Alerts", systemImage: "exclamationmark.triangle") }
                .badge(model.report?.alerts.count ?? 0)
                .tag(AppTab.alerts)
            LocationsView()
                .tabItem { Label("Locations", systemImage: "mappin.and.ellipse") }
                .tag(AppTab.locations)
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gear") }
                .tag(AppTab.settings)
        }
        .task {
            await model.requestNotificationsOnFirstLaunch()
            await model.refresh(announce: false)
        }
        .onChange(of: router.pendingAlert, initial: true) { _, request in
            guard let request else { return }
            router.pendingAlert = nil
            tab = .alerts
            Task { await model.openAlert(request) }
        }
    }
}
