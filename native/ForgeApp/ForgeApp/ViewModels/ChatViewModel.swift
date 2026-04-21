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

    func react(messageId: Int, emoji: String) async {
        guard let idx = messages.firstIndex(where: { $0.id == messageId }) else { return }
        // Optimistic local toggle
        var msg = messages[idx]
        if let reactionIdx = msg.reactions.firstIndex(where: { $0.emoji == emoji }) {
            var r = msg.reactions[reactionIdx]
            let wasMe = r.reactedByMe
            let newCount = r.count + (wasMe ? -1 : 1)
            if newCount <= 0 {
                msg.reactions.remove(at: reactionIdx)
            } else {
                msg.reactions[reactionIdx] = ReactionSummary(emoji: emoji, count: newCount, reactedByMe: !wasMe)
            }
        } else {
            msg.reactions.append(ReactionSummary(emoji: emoji, count: 1, reactedByMe: true))
        }
        messages[idx] = msg

        // Confirm with server and apply authoritative state
        do {
            let updated = try await api.toggleReaction(workspaceId: workspaceId, channelId: channelId, messageId: messageId, emoji: emoji)
            if let confirmedIdx = messages.firstIndex(where: { $0.id == messageId }) {
                messages[confirmedIdx].reactions = updated
            }
        } catch { /* silent – optimistic state stays */ }
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

    /// The email of the other participant (for DM FaceTime calls).
    /// Returns nil if there's no clear other user (e.g. group channel).
    var otherUserEmail: String? {
        let myId = messages.first(where: { $0.author != nil })?.userId
        let others = Set(messages.compactMap { msg -> String? in
            guard msg.userId != myId, let email = msg.author?.email else { return nil }
            return email
        })
        return others.count == 1 ? others.first : nil
    }
}
