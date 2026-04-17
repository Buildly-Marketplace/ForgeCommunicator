import Foundation
import Combine

/// Global app state shared across views.
@MainActor
final class AppState: ObservableObject {
    @Published var currentWorkspaceId: Int?
    @Published var unreadTotal: Int = 0
    @Published var isConnected: Bool = false
}
