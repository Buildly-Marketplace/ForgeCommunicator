import SwiftUI
import AppKit

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
        if Bundle.main.bundleIdentifier != nil {
            NotificationService.configure()
            NotificationService.requestAuthorization()
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
