import SwiftUI

/// Reusable branded navigation header with the Forge Communicator logo.
struct ForgeNavHeader: View {
    var title: String = ""

    var body: some View {
        HStack(spacing: 8) {
            // Logo badge
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [ForgeTheme.primary, ForgeTheme.accent],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 28, height: 28)

                Image(systemName: "bolt.fill")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(.white)
            }

            Text(title.isEmpty ? "ForgeCommunicator" : title)
                .font(.headline.bold())
                .foregroundStyle(.white)
        }
    }
}

/// Toolbar modifier that places the Forge logo in the top-leading corner.
struct ForgeLogoToolbar: ViewModifier {
    var title: String = ""

    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItem(placement: .principal) {
                    ForgeNavHeader(title: title)
                }
            }
    }
}

extension View {
    func forgeLogoToolbar(title: String = "") -> some View {
        modifier(ForgeLogoToolbar(title: title))
    }
}
