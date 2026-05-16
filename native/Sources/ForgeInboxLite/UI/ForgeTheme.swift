import SwiftUI

enum ForgeTheme {
    static let primary = Color(red: 0.302, green: 0.714, blue: 1.000)
    static let accent = Color(red: 1.000, green: 0.784, blue: 0.341)
    static let amber = accent
    static let cyan = primary
    static let silver = Color(red: 0.902, green: 0.918, blue: 0.945)

    static let dark950 = Color(red: 0.043, green: 0.059, blue: 0.090)
    static let dark900 = Color(red: 0.067, green: 0.094, blue: 0.153)
    static let dark800 = Color(red: 0.106, green: 0.149, blue: 0.220)
    static let dark700 = Color(red: 0.176, green: 0.227, blue: 0.314)

    static let glassBorder = silver.opacity(0.12)
    static let glassBorderActive = primary.opacity(0.34)
    static let glassFill = dark800.opacity(0.72)
    static let overlayFill = dark950.opacity(0.72)

    static let brandGradient = LinearGradient(
        colors: [primary, Color(red: 0.110, green: 0.340, blue: 0.720)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let deviceGradient = LinearGradient(
        colors: [
            Color(red: 0.290, green: 0.275, blue: 0.248),
            dark950,
            dark800,
        ],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let shellGradient = LinearGradient(
        colors: [dark950, dark900, dark800],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static func brandFont(size: CGFloat, weight: Font.Weight = .bold) -> Font {
        .custom("Orbitron", size: size).weight(weight)
    }
}
