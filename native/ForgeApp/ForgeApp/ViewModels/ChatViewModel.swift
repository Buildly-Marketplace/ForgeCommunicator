import Foundation
import Combine

@MainActor
final class ChatViewModel: ObservableObject {
    let channelId: Int
    let workspaceId: Int

    @Published var messages: [MessageResponse] = []
    @Published var isLoading = false
    @Published var isSending = false
    @Published var error: String?

    private let api = APIClient.shared

    init(channelId: Int, workspaceId: Int) {
        self.channelId = channelId
        self.workspaceId = workspaceId
    }

    func loadInitial() async {
        isLoading = messages.isEmpty
        defer { isLoading = false }
        do {
            messages = try await api.messages(workspaceId: workspaceId, channelId: channelId)
            try? await api.markRead(workspaceId: workspaceId, channelId: channelId)
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Load older messages (scroll up).
    func loadOlder() async {
        guard let first = messages.first else { return }
        do {
            let older = try await api.messages(workspaceId: workspaceId, channelId: channelId, before: first.id)
            if !older.isEmpty {
                messages.insert(contentsOf: older, at: 0)
            }
        } catch { /* silent */ }
    }

    /// Catch up with new messages (polling / after WS hint).
    func catchUp() async {
        guard let last = messages.last else { return }
        do {
            let newer = try await api.messages(workspaceId: workspaceId, channelId: channelId, after: last.id)
            if !newer.isEmpty {
                messages.append(contentsOf: newer)
                try? await api.markRead(workspaceId: workspaceId, channelId: channelId)
            }
        } catch { /* silent */ }
    }

    func send(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        isSending = true
        defer { isSending = false }
        do {
            let msg = try await api.sendMessage(workspaceId: workspaceId, channelId: channelId, body: trimmed)
            messages.append(msg)
        } catch {
            self.error = error.localizedDescription
        }
    }
}
