import Foundation
import Combine

@MainActor
final class ConversationListViewModel: ObservableObject {
    @Published var conversations: [ConversationPreview] = []
    @Published var isLoading = false
    @Published var error: String?

    private let api = APIClient.shared

    func load() async {
        isLoading = conversations.isEmpty
        error = nil
        defer { isLoading = false }

        do {
            // include_channels=true gives us the full inbox
            conversations = try await api.conversations(includeChannels: true)
        } catch {
            self.error = error.localizedDescription
        }
    }
}
