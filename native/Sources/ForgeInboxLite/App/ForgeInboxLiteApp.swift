import SwiftUI
import AppKit
import UserNotifications

// MARK: - RailHostView
// A self-contained SwiftUI view that owns AccountStore and a per-source
// NativeCommunicatorStore, suitable for embedding in the floating rail panel.

private struct RailHostView: View {
    @StateObject private var accountStore = AccountStore()
    @State private var communicatorStore: NativeCommunicatorStore?

    var body: some View {
        Group {
            if let store = communicatorStore {
                ConversationRailView(
                    store: store,
                    accountStore: accountStore,
                    selectedSourceID: $accountStore.selectedSourceID,
                    onOpenConversation: { conversation in
                        IMWindowManager.shared.openConversation(conversation, store: store)
                    },
                    onOpenSettings: {
                        // Open the full workspace window on demand.
                        NSApp.setActivationPolicy(.regular)
                        NSApp.activate(ignoringOtherApps: true)
                    }
                )
            } else {
                VStack(spacing: 12) {
                    ForgeLogoIcon(size: 36)
                    Text("No account configured")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .onAppear {
            accountStore.load()
        }
        .onChange(of: accountStore.selectedAccountID) { _ in
            rebuildStore()
        }
        .onChange(of: accountStore.accounts) { _ in
            if communicatorStore == nil {
                rebuildStore()
            }
        }
    }

    private func rebuildStore() {
        guard let source = accountStore.selectedSource else {
            communicatorStore = nil
            return
        }
        communicatorStore = NativeCommunicatorStore(source: source)
    }
}

// MARK: - RailWindowController

final class RailWindowController: NSObject {
    private var panel: NSPanel?

    func createAndShow() {
        guard let screen = NSScreen.main else { return }

        let screenFrame = screen.frame
        let visibleFrame = screen.visibleFrame
        let panelWidth: CGFloat = 260
        let panelHeight = visibleFrame.height
        let panelX = screenFrame.maxX - panelWidth
        let panelY = visibleFrame.minY

        let p = NSPanel(
            contentRect: NSRect(x: panelX, y: panelY, width: panelWidth, height: panelHeight),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        p.isFloatingPanel = true
        p.hidesOnDeactivate = false
        p.level = .floating
        p.collectionBehavior = [.canJoinAllSpaces, .stationary]
        p.isOpaque = false
        p.backgroundColor = .clear

        let hosting = NSHostingView(rootView: RailHostView())
        hosting.frame = NSRect(x: 0, y: 0, width: panelWidth, height: panelHeight)
        p.contentView = hosting

        self.panel = p
        p.orderFrontRegardless()
    }

    func show() {
        panel?.orderFrontRegardless()
    }

    func hide() {
        panel?.orderOut(nil)
    }

    func toggle() {
        guard let p = panel else { return }
        if p.isVisible { hide() } else { show() }
    }
}

// MARK: - AppDelegate

private final class AppDelegate: NSObject, NSApplicationDelegate {

    let railController = RailWindowController()

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Start as accessory so no main SwiftUI window appears automatically.
        NSApp.setActivationPolicy(.accessory)

        // Close any windows SwiftUI auto-opened before we suppressed them.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            for window in NSApp.windows where !(window is NSPanel) {
                window.close()
            }
        }

        NotificationCenter.default.addObserver(
            forName: NSWindow.didBecomeMainNotification,
            object: nil,
            queue: .main
        ) { _ in
            self.applyWorkspaceWindowStyle()
        }

        // Show the rail panel on launch.
        railController.createAndShow()
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        UNUserNotificationCenter.current().setBadgeCount(0) { _ in }
    }

    /// Call this when the user explicitly opens the full workspace window.
    func openWorkspace() {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        applyWorkspaceWindowStyle()
    }

    private func applyWorkspaceWindowStyle() {
        for window in NSApp.windows where !(window is NSPanel) {
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

// MARK: - App

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
        // Full workspace window — not shown by default, opened on demand via menu or settings.
        WindowGroup {
            ForgeCommunicatorShellView()
                .frame(minWidth: 980, minHeight: 620)
                .onAppear {
                    appDelegate.openWorkspace()
                }
        }
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandMenu("Communicator") {
                Button("Show Rail") {
                    appDelegate.railController.toggle()
                }
                .keyboardShortcut("f", modifiers: [.command, .shift])

                Divider()

                Button("Open Workspace") {
                    appDelegate.openWorkspace()
                }
                .keyboardShortcut("0", modifiers: [.command, .shift])
            }
        }
    }
}
