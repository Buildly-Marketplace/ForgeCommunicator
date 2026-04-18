import SwiftUI

/// Reusable branded navigation header with the Forge Communicator logo.
struct ForgeNavHeader: View {
    var title: String = ""

    var body: some View {
        HStack(spacing: 8) {
            Image("AppIcon")
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 28, height: 28)
                .clipShape(Circle())

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
