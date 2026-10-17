import SwiftUI

struct AlertsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        NavigationStack {
            Group {
                if model.selectedLocation == nil {
                    EmptyStateView(title: "No Locations Yet", systemImage: "mappin.slash", description: "Add a location on the Locations tab to see its alerts.")
                } else if let report = model.report {
                    if report.alerts.isEmpty {
                        EmptyStateView(
                            title: "No active alerts",
                            systemImage: "checkmark.shield",
                            description: report.sourceDescription.hasPrefix("National")
                                 ? "There are no active National Weather Service alerts for \(report.location.name)."
                                 : "Alerts are only available for United States locations through the National Weather Service.")
                    } else {
                        List(report.alerts) { alert in
                            NavigationLink(value: alert) {
                                AlertRow(alert: alert)
                            }
                            .accessibilityHint("Opens the full alert text")
                        }
                        .navigationDestination(for: WeatherAlert.self) { alert in
                            AlertDetailView(alert: alert, formatter: WeatherFormatter(settings: settings, timeZone: report.timeZone))
                        }
                    }
                } else if model.isLoading {
                    ProgressView("Loading alerts…")
                } else if let message = model.errorMessage {
                    EmptyStateView(title: "Alerts Unavailable", systemImage: "exclamationmark.triangle", description: message)
                } else {
                    EmptyStateView(title: "No active alerts", systemImage: "checkmark.shield")
                }
            }
            .navigationTitle("Alerts")
            .refreshable {
                await model.refresh(force: true)
            }
        }
    }
}

struct AlertRow: View {
    let alert: WeatherAlert

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(alert.event)
                .font(.headline)
            Text(alert.severity)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            if let headline = alert.headline {
                Text(headline)
                    .font(.subheadline)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(alert.event), \(alert.severity) severity" + (alert.headline.map { ". \($0)" } ?? ""))
    }
}

struct AlertDetailView: View {
    let alert: WeatherAlert
    let formatter: WeatherFormatter

    var body: some View {
        List {
            Section {
                MeasurementRow(label: "Severity", value: alert.severity)
                if let urgency = alert.urgency { MeasurementRow(label: "Urgency", value: urgency) }
                if let certainty = alert.certainty { MeasurementRow(label: "Certainty", value: certainty) }
                if let effective = formatter.dateTime(alert.effective) { MeasurementRow(label: "Effective", value: effective) }
                if let expires = formatter.dateTime(alert.expires) { MeasurementRow(label: "Expires", value: expires) }
                if let sender = alert.sender { MeasurementRow(label: "Issued by", value: sender) }
            } header: {
                SectionHeader(alert.event)
            }
            if let headline = alert.headline {
                Section {
                    Text(headline)
                } header: {
                    SectionHeader("Headline")
                }
            }
            if let area = alert.areaDescription {
                Section {
                    Text(area)
                } header: {
                    SectionHeader("Areas Affected")
                }
            }
            if let description = alert.description {
                Section {
                    Text(description)
                        .textSelection(.enabled)
                } header: {
                    SectionHeader("Description")
                }
            }
            if let instruction = alert.instruction {
                Section {
                    Text(instruction)
                        .textSelection(.enabled)
                } header: {
                    SectionHeader("Instructions")
                }
            }
        }
        .navigationTitle(alert.event)
        .navigationBarTitleDisplayMode(.inline)
    }
}
