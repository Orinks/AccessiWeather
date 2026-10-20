import SwiftUI

/// Empty/unavailable state whose icon is decorative, so VoiceOver reads only the title and description.
struct EmptyStateView: View {
    let title: String
    let systemImage: String
    var description: String?

    var body: some View {
        ContentUnavailableView {
            Label {
                Text(title)
                    .accessibilityAddTraits(.isHeader)
            } icon: {
                Image(systemName: systemImage)
                    .accessibilityHidden(true)
            }
        } description: {
            if let description {
                Text(description)
            }
        }
    }
}
