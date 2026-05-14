import AuthenticationServices
#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

/// Provides the presentation anchor for ASWebAuthenticationSession on both iOS and macOS.
/// Also retains the session for the duration of the OAuth flow.
final class OAuthPresentationContext: NSObject, ASWebAuthenticationPresentationContextProviding {
    static let shared = OAuthPresentationContext()
    private var retainedSession: ASWebAuthenticationSession?

    func retain(_ session: ASWebAuthenticationSession) {
        retainedSession = session
    }

    func clear() {
        retainedSession = nil
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        #if canImport(UIKit)
        // Return the key window of the first connected scene
        let scene = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }
        return scene?.windows.first { $0.isKeyWindow } ?? ASPresentationAnchor()
        #elseif canImport(AppKit)
        return NSApplication.shared.windows.first { $0.isKeyWindow } ?? NSWindow()
        #endif
    }
}
