import Foundation
#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

/// Helper for initiating FaceTime calls via URL schemes.
/// Works on iOS/macOS when FaceTime is available. Uses the contact's email
/// as the identifier — both parties must have FaceTime enabled with that email.
enum FaceTimeHelper {

    /// Start a FaceTime video call.
    static func videoCall(email: String) {
        open(scheme: "facetime", identifier: email)
    }

    /// Start a FaceTime audio call.
    static func audioCall(email: String) {
        open(scheme: "facetime-audio", identifier: email)
    }

    /// Check if FaceTime is available on this device.
    static var isAvailable: Bool {
        guard let url = URL(string: "facetime://test@test.com") else { return false }
        #if canImport(UIKit)
        return UIApplication.shared.canOpenURL(url)
        #elseif canImport(AppKit)
        return NSWorkspace.shared.urlForApplication(toOpen: url) != nil
        #else
        return false
        #endif
    }

    private static func open(scheme: String, identifier: String) {
        guard let encoded = identifier.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "\(scheme)://\(encoded)") else { return }
        #if canImport(UIKit)
        UIApplication.shared.open(url)
        #elseif canImport(AppKit)
        NSWorkspace.shared.open(url)
        #endif
    }
}
