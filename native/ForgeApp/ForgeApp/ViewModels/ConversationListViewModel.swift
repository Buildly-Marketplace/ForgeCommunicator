import Foundation
import Combine

@MainActor
final class ConversationListViewModel: ObservableObject {
    @Published var conversations: [ConversationPreview] = []
    @Published var isLoading = false
    @Published var error: String?

    private let api = APIClient.shared
    private var hasSyncedSlack = false

    func load() async {
        isLoading = conversations.isEmpty
        error = nil
        defer { isLoading = false }

        do {
            let loaded = try await api.conversations(includeChannels: true)
            conversations = loaded

            // Auto-sync Slack channels if connected but none bridged yet
            if !hasSyncedSlack && !conversations.contains(where: { $0.bridgedPlatform == "slack" }) {
                await autoSyncSlackIfNeeded()
            }
        } catch {
            print("[ConversationListVM] ERROR: \(error)")
            self.error = error.localizedDescription
        }
    }

    private func autoSyncSlackIfNeeded() async {
        hasSyncedSlack = true
        do {
            let status = try await api.integrationStatus()
            guard status.slackConnected else { return }

            // Get workspaces and sync to each one
            let workspaces = try await api.workspaces()
            var didSync = false
            for ws in workspaces {
                let result = try await api.syncSlackChannels(workspaceId: ws.id)
                if result.synced > 0 { didSync = true }
            }

            // Reload conversations if we synced anything
            if didSync {
                conversations = try await api.conversations(includeChannels: true)
            }
        } catch {
            // Sync failure is non-fatal — don't overwrite the main error
            // Sync failure is non-fatal
        }
    }
}
