import SwiftUI

struct EventCenterView: View {
    @EnvironmentObject private var model: AppModel
    @State private var showingClearConfirmation = false

    var body: some View {
        List {
            Section {
                if model.eventLog.entries.isEmpty {
                    Text("No events yet.")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(model.eventLog.entries) { entry in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(entry.accessibleSummary)
                                .font(.body)
                            if !entry.detail.isEmpty {
                                Text(entry.detail)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(entry.accessibleSummary)
                        .accessibilityValue(entry.detail)
                    }
                }
            } header: {
                SectionHeader("Events")
            }
        }
        .navigationTitle("Event Center")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button("Clear", role: .destructive) {
                    showingClearConfirmation = true
                }
                .disabled(model.eventLog.entries.isEmpty)
                .accessibilityHint("Removes all saved events")
            }
        }
        .confirmationDialog(
            "Clear all events?",
            isPresented: $showingClearConfirmation,
            titleVisibility: .visible
        ) {
            Button("Clear", role: .destructive) {
                model.eventLog.clear()
            }
            Button("Cancel", role: .cancel) {}
        }
    }
}
