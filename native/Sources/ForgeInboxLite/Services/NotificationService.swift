import Foundation
import UserNotifications

enum NotificationService {
    private static let deduper = NotificationDeduper()

    static func configure() {
        UNUserNotificationCenter.current().delegate = NotificationCenterDelegate.shared
    }

    static func requestAuthorization() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if let error {
                print("Notification permission request failed: \(error)")
            }
            if !granted {
                print("Notification permission not granted")
            }
        }
    }

    static func post(title: String, body: String, sound: UNNotificationSound = .default) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = sound

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error {
                print("Failed to post notification: \(error)")
            }
        }
    }

    static func postSourceActivity(
        sourceID: UUID,
        sourceName: String,
        providerName: String,
        body: String,
        dedupeHint: String,
        minimumInterval: TimeInterval = 20,
        sound: UNNotificationSound = .default
    ) {
        let normalizedBody = body.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedBody.isEmpty else { return }

        let normalizedProvider = providerName.lowercased()
        let normalizedHint = dedupeHint.lowercased()
        let normalizedBodyKey = normalizedBody.lowercased()
        let key = "\(sourceID.uuidString)|\(normalizedProvider)|\(normalizedBodyKey)|\(normalizedHint)"
        let crossEmitterKey = "\(sourceID.uuidString)|\(normalizedProvider)|\(normalizedBodyKey)"
        Task {
            let shouldDeliverSpecific = await deduper.shouldDeliver(key: key, minimumInterval: minimumInterval)
            let shouldDeliverCrossEmitter = await deduper.shouldDeliver(key: crossEmitterKey, minimumInterval: minimumInterval)
            guard shouldDeliverSpecific && shouldDeliverCrossEmitter else { return }

            await MainActor.run {
                post(
                    title: "\(sourceName) • \(providerName)",
                    body: normalizedBody,
                    sound: sound
                )
            }
        }
    }
}

private actor NotificationDeduper {
    private var lastDeliveryByKey: [String: Date] = [:]

    func shouldDeliver(key: String, minimumInterval: TimeInterval) -> Bool {
        let now = Date()
        if let previous = lastDeliveryByKey[key], now.timeIntervalSince(previous) < minimumInterval {
            return false
        }

        lastDeliveryByKey[key] = now
        return true
    }
}

private final class NotificationCenterDelegate: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationCenterDelegate()

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .list, .sound, .badge])
    }
}
