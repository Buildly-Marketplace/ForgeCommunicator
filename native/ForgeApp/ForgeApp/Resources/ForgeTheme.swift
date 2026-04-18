import SwiftUI

/// Brand colors and theme matching the ForgeCommunicator web design.
/// Web CSS references:
///   --brand-primary: #3b82f6  (Blue-500)
///   --brand-secondary: #0f172a (Slate-900)
///   --brand-accent: #a855f7   (Purple-500)
enum ForgeTheme {
    // MARK: - Brand Colors

    /// Main accent — buttons, links, highlights (#3b82f6)
    static let primary = Color(red: 0.231, green: 0.510, blue: 0.965)

    /// Dark navy background base (#0f172a)
    static let secondary = Color(red: 0.059, green: 0.090, blue: 0.165)

    /// Purple highlight (#a855f7)
    static let accent = Color(red: 0.659, green: 0.333, blue: 0.969)

    // MARK: - Dark Backgrounds (from web `.dark` palette)

    /// Deepest background (#050d1a)
    static let dark950 = Color(red: 0.020, green: 0.051, blue: 0.102)

    /// Main page background (#0a1628)
    static let dark900 = Color(red: 0.039, green: 0.086, blue: 0.157)

    /// Card / elevated surface (#0f172a)
    static let dark800 = Color(red: 0.059, green: 0.090, blue: 0.165)

    /// Sidebar / panel (#1a2744)
    static let dark700 = Color(red: 0.102, green: 0.153, blue: 0.267)

    /// Dividers / borders (#1e293b)
    static let dark600 = Color(red: 0.118, green: 0.161, blue: 0.231)

    /// Muted foreground elements (#334155)
    static let dark500 = Color(red: 0.200, green: 0.255, blue: 0.333)

    // MARK: - Text

    static let textPrimary = Color.white
    static let textSecondary = Color(red: 0.596, green: 0.631, blue: 0.702) // gray-400 equivalent
    static let textMuted = Color(red: 0.392, green: 0.431, blue: 0.502) // gray-500 equivalent

    // MARK: - Gradient (matches web `splash-bg` / `forge-bg`)

    /// The main background gradient used on the login page and app chrome.
    static let backgroundGradient = LinearGradient(
        colors: [dark900, dark700, dark800],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    // MARK: - Glass Panel (matches web `login-form-panel`)

    /// Glassmorphism card style: semi-transparent with blur.
    struct GlassPanel: ViewModifier {
        func body(content: Content) -> some View {
            content
                .background(.ultraThinMaterial.opacity(0.35))
                .background(Color.white.opacity(0.03))
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                )
        }
    }

    // MARK: - Input Style (matches web dark inputs)

    struct DarkInputStyle: ViewModifier {
        func body(content: Content) -> some View {
            content
                .textFieldStyle(.plain)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .foregroundStyle(.white)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.white.opacity(0.05))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                )
                .contentShape(RoundedRectangle(cornerRadius: 12))
        }
    }
}

// MARK: - Convenience modifiers

extension View {
    func forgeGlassPanel() -> some View {
        modifier(ForgeTheme.GlassPanel())
    }

    func forgeDarkInput() -> some View {
        modifier(ForgeTheme.DarkInputStyle())
    }
}
