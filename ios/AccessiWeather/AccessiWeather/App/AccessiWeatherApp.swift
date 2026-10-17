import SwiftUI

@main
struct AccessiWeatherApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = AppModel.shared
    @Environment(\.scenePhase) private var scenePhase

    init() {
        NotificationRouter.shared.install()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
                .environmentObject(model.settings)
                .environmentObject(model.locationStore)
        }
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .active:
                model.startAutoRefresh()
                model.updateCurrentLocation()
            case .background: model.didEnterBackground()
            default: break
            }
        }
        .backgroundTask(.appRefresh(BackgroundRefresh.taskIdentifier)) {
            await model.handleBackgroundRefresh()
        }
    }
}
