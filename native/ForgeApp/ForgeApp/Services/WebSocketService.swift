import Foundation
import Combine

/// WebSocket service for real-time message updates.
/// Connects to the ForgeCommunicator WebSocket endpoint and receives JSON events.
@MainActor
final class WebSocketService: ObservableObject {
    @Published var isConnected = false

    private var task: URLSessionWebSocketTask?
    private var session: URLSession
    private var cancellable: AnyCancellable?

    /// Callback when a new message arrives on a channel.
    var onNewMessage: ((Int, Int) -> Void)? // (channelId, messageId)

    init() {
        self.session = URLSession(configuration: .default)
    }

    func connect(channelId: Int) {
        disconnect()

        // Build WS URL
        let scheme: String
        let host: String
        #if DEBUG
        scheme = "ws"
        host = "localhost:8000"
        #else
        scheme = "wss"
        host = "your-forge-instance.com"
        #endif

        guard var components = URLComponents(string: "\(scheme)://\(host)/ws/\(channelId)") else { return }
        if let token = KeychainService.loadToken() {
            components.queryItems = [URLQueryItem(name: "token", value: token)]
        }
        guard let url = components.url else { return }

        task = session.webSocketTask(with: url)
        task?.resume()
        isConnected = true
        receiveLoop()
    }

    func disconnect() {
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        isConnected = false
    }

    private func receiveLoop() {
        task?.receive { [weak self] result in
            Task { @MainActor in
                guard let self else { return }
                switch result {
                case .success(let msg):
                    self.handleMessage(msg)
                    self.receiveLoop()
                case .failure:
                    self.isConnected = false
                    // Reconnect after delay
                    try? await Task.sleep(for: .seconds(3))
                    if self.task != nil { self.receiveLoop() }
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        guard case .string(let text) = message,
              let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }

        switch type {
        case "new_message":
            if let channelId = json["channel_id"] as? Int ?? (json["channel_id"] as? String).flatMap(Int.init),
               let messageId = json["message_id"] as? Int ?? (json["message_id"] as? String).flatMap(Int.init) {
                onNewMessage?(channelId, messageId)
            }
        default:
            break
        }
    }
}
