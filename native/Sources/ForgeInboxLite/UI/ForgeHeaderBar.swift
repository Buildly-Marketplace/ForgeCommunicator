import SwiftUI

struct ForgeHeaderBar: View {
    let title: String
    var subtitle: String? = nil

    var body: some View {
        HStack(spacing: 10) {
            ForgeBadgeIcon(size: 26)

            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(ForgeTheme.brandFont(size: 13, weight: .bold))
                    .tracking(1.6)
                    .textCase(.uppercase)
                    .foregroundStyle(ForgeTheme.silver)
                if let subtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(
            ZStack {
                ForgeTheme.dark950.opacity(0.90)

                LinearGradient(
                    colors: [ForgeTheme.dark700.opacity(0.38), Color.clear],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            }
        )
        .overlay(Rectangle().fill(ForgeTheme.amber.opacity(0.18)).frame(height: 1), alignment: .bottom)
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(ForgeTheme.glassBorder, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
