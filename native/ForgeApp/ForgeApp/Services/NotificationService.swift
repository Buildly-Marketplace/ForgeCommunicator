import Foundation
import UserNotifications
#if canImport(AppKit)
import AppKit
#endif
#if canImport(AVFoundation)
import AVFoundation
#endif

/// Manages local + push notifications, badge count, and notification sounds.
@MainActor
final class NotificationService: ObservableObject {
    static let shared = NotificationService()

    @Published var unreadCount: Int = 0 {
        didSet { updateBadge() }
    }
    @Published var isAuthorized = false

    private var audioPlayer: AVAudioPlayer?

    func requestPermission() async {
        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            isAuthorized = granted
        } catch {
            isAuthorized = false
        }
    }

    /// Post a local notification (e.g. new DM while backgrounded).
    func postLocal(title: String, body: String, threadId: String? = nil, url: String? = nil) {
        guard isAuthorized else { return }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        if let threadId { content.threadIdentifier = threadId }
        if let url {
            content.userInfo["url"] = url
        }
        // Badge
        unreadCount += 1
        content.badge = NSNumber(value: unreadCount)

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil // deliver immediately
        )
        UNUserNotificationCenter.current().add(request)
    }

    /// Play the notification chirp sound in-app.
    func playSound() {
        // Use system sound as fallback
        #if canImport(AppKit)
        NSSound.beep()
        #endif
    }

    func clearBadge() {
        unreadCount = 0
        updateBadge()
        UNUserNotificationCenter.current().removeAllDeliveredNotifications()
    }

    func increment() {
        unreadCount += 1
    }

    private func updateBadge() {
        #if canImport(UIKit)
        UIApplication.shared.applicationIconBadgeNumber = unreadCount
        #endif
        // macOS dock badge
        #if canImport(AppKit)
        if unreadCount > 0 {
            NSApplication.shared.dockTile.badgeLabel = "\(unreadCount)"
        } else {
            NSApplication.shared.dockTile.badgeLabel = nil
        }
        #endif
    }
}
