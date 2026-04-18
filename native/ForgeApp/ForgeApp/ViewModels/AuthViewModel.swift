import Foundation
import Combine

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: UserResponse?
    @Published var isLoading = false
    @Published var error: String?

    private let api = APIClient.shared

    /// Try to restore a saved session from the Keychain.
    func restoreSession() async {
        guard KeychainService.loadToken() != nil else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            let user = try await api.me()
            currentUser = user
            isAuthenticated = true
        } catch {
            // Token expired or invalid — clear it
            KeychainService.delete()
            isAuthenticated = false
        }
    }

    func login(email: String, password: String) async {
        isLoading = true
        error = nil
        defer { isLoading = false }

        do {
            let response = try await api.login(email: email, password: password)
            KeychainService.saveToken(response.token)
            currentUser = response.user
            isAuthenticated = true
        } catch let apiError as APIError {
            error = apiError.localizedDescription
        } catch {
            self.error = error.localizedDescription
        }
    }

    func register(email: String, password: String, displayName: String) async {
        isLoading = true
        error = nil
        defer { isLoading = false }

        do {
            let response = try await api.register(email: email, password: password, displayName: displayName)
            KeychainService.saveToken(response.token)
            currentUser = response.user
            isAuthenticated = true
        } catch let apiError as APIError {
            error = apiError.localizedDescription
        } catch {
            self.error = error.localizedDescription
        }
    }

    func logout() async {
        do { try await api.logout() } catch { /* best effort */ }
        KeychainService.delete()
        currentUser = nil
        isAuthenticated = false
    }

    func refreshProfile() async {
        do {
            currentUser = try await api.me()
        } catch { /* silent */ }
    }

    func handleOAuthToken(_ token: String) async {
        KeychainService.saveToken(token)
        do {
            let user = try await api.me()
            currentUser = user
            isAuthenticated = true
        } catch {
            KeychainService.delete()
            self.error = "OAuth sign-in failed"
        }
    }
}
