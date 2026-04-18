import SwiftUI

/// Reusable branded navigation header with the Forge Communicator logo.
struct ForgeNavHeader: View {
    var title: String = ""

    var body: some View {
        HStack(spacing: 10) {
            ForgeLogoImage(size: 28)

            Text(title.isEmpty ? "ForgeCommunicator" : title)
                .font(.headline.bold())
                .foregroundStyle(.white)
        }
    }
}

/// Loads the ForgeCommunicator logo from the SwiftPM resource bundle.
struct ForgeLogoImage: View {
    var size: CGFloat = 28

    var body: some View {
        Image("ForgeLogo", bundle: .module)
            .resizable()
            .interpolation(.high)
            .antialiased(true)
            .aspectRatio(contentMode: .fit)
            .frame(width: size, height: size)
            .clipShape(RoundedRectangle(cornerRadius: size * 0.2))
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
