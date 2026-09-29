import SwiftUI

struct EventCenterView: View {
    @EnvironmentObject private var model: AppModel
    @State private var showingClearConfirmation = false

    var body: some View {
        List {
            Section {
                if model.eventLog.entries.isEmpty {
                    Text("No events yet.")
                        .foregroundStyle(.primary)
                } else {
                    ForEach(model.eventLog.entries) { entry in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(entry.accessibleSummary)
                                .font(.body)
                            if !entry.detail.isEmpty {
                                Text(entry.detail)
                                    .font(.subheadline)
                                    .foregroundStyle(.primary)
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
                Button {
                    showingClearConfirmation = true
                } label: {
                    Image(systemName: "trash")
                }
                .foregroundStyle(.primary)
                .disabled(model.eventLog.entries.isEmpty)
                .accessibilityLabel("Clear")
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
