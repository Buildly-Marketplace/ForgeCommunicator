import SwiftUI

struct ForgeGlassSurface: ViewModifier {
    func body(content: Content) -> some View {
        content
            .background(.ultraThinMaterial.opacity(0.30))
            .background(
                LinearGradient(
                    colors: [ForgeTheme.dark700.opacity(0.48), ForgeTheme.overlayFill],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(ForgeTheme.glassBorder, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.32), radius: 22, x: 0, y: 14)
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

extension View {
    func forgeGlassSurface() -> some View {
        modifier(ForgeGlassSurface())
    }
}
