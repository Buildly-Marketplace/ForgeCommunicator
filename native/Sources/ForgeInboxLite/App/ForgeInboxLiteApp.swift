import SwiftUI
import AppKit
import UserNotifications

private final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.activate(ignoringOtherApps: true)
        applyWindowStyle()

        NotificationCenter.default.addObserver(
            forName: NSWindow.didBecomeMainNotification,
            object: nil,
            queue: .main
        ) { _ in
            self.applyWindowStyle()
        }
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        // Clear the dock badge whenever the user brings the app to front.
        UNUserNotificationCenter.current().setBadgeCount(0) { _ in }
    }

    private func applyWindowStyle() {
        for window in NSApp.windows {
            window.titleVisibility = .hidden
            window.titlebarAppearsTransparent = true
            window.styleMask.insert(.fullSizeContentView)
            window.isOpaque = false
            window.backgroundColor = .black
            window.toolbar?.showsBaselineSeparator = false
            window.toolbar = nil
            window.titlebarSeparatorStyle = .none
            window.isMovableByWindowBackground = true
        }
    }
}

@main
struct ForgeInboxLiteApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    init() {
        NotificationService.configure()
        NotificationService.requestAuthorization()

        if Bundle.main.bundleIdentifier == nil {
            print("[ForgeInboxLite] Running outside an app bundle; macOS notifications may be limited.")
        }
    }

    var body: some Scene {
        WindowGroup {
            ForgeCommunicatorShellView()
                .frame(minWidth: 980, minHeight: 620)
        }
        .windowStyle(.hiddenTitleBar)
    }
}
