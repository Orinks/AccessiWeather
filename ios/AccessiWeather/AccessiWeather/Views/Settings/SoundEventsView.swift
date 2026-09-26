import SwiftUI

/// Per-event sound toggles, mirroring the desktop app's `muted_sound_events` setting.
struct SoundEventsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        Form {
            Section {
                ForEach(SoundEvent.appEvents) { event in
                    eventRow(event)
                }
            } header: {
                SectionHeader("App Events")
            }
            Section {
                ForEach(SoundEvent.alertEvents) { event in
                    eventRow(event)
                }
            } header: {
                SectionHeader("Alert Severity")
            } footer: {
                Text("Alert sounds play in the app when a new alert appears and are used for notifications of that severity.")
            }
        }
        .navigationTitle("Sound Events")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func eventRow(_ event: SoundEvent) -> some View {
        HStack {
            Toggle(event.title, isOn: Binding(
                get: { !settings.isMuted(event) },
                set: { settings.setMuted(!$0, for: event) }
            ))
            .accessibilityHint("Off mutes this sound")
            Button {
                if let pack = model.sounds.selectedPack, let url = pack.url(for: event) {
                    model.sounds.previewClip(at: url)
                }
            } label: {
                Image(systemName: "play.circle")
                    .imageScale(.large)
            }
            .buttonStyle(.borderless)
            .accessibilityLabel("Preview \(event.title) sound")
        }
    }
}
