import SwiftUI

struct ForgeBadgeIcon: View {
    var size: CGFloat = 28

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.24, style: .continuous)
                .fill(ForgeTheme.deviceGradient)
                .overlay(
                    RoundedRectangle(cornerRadius: size * 0.24, style: .continuous)
                        .stroke(ForgeTheme.silver.opacity(0.22), lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.38), radius: size * 0.36, x: 0, y: size * 0.12)
                .shadow(color: ForgeTheme.primary.opacity(0.18), radius: size * 0.36, x: 0, y: 0)

            RoundedRectangle(cornerRadius: size * 0.10, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [ForgeTheme.dark900, ForgeTheme.dark950],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: size * 0.10, style: .continuous)
                        .stroke(ForgeTheme.primary.opacity(0.20), lineWidth: 1)
                )
                .frame(width: size * 0.52, height: size * 0.56)
                .offset(y: -size * 0.06)

            HStack(spacing: max(size * 0.035, 1.2)) {
                WaveBar(height: size * 0.18, color: ForgeTheme.primary.opacity(0.76))
                WaveBar(height: size * 0.30, color: ForgeTheme.primary)
                WaveBar(height: size * 0.42, color: ForgeTheme.amber)
                WaveBar(height: size * 0.29, color: ForgeTheme.primary)
                WaveBar(height: size * 0.20, color: ForgeTheme.primary.opacity(0.82))
            }
            .offset(y: -size * 0.06)

            HStack(spacing: size * 0.10) {
                Capsule().fill(ForgeTheme.primary)
                Capsule().fill(ForgeTheme.amber)
                Capsule().fill(ForgeTheme.silver.opacity(0.52))
            }
            .frame(width: size * 0.44, height: size * 0.055)
            .offset(y: size * 0.34)
        }
        .frame(width: size, height: size)
    }
}

private struct WaveBar: View {
    let height: CGFloat
    let color: Color

    var body: some View {
        Capsule()
            .fill(color)
            .frame(width: 2, height: height)
            .shadow(color: color.opacity(0.62), radius: 4, x: 0, y: 0)
    }
}
