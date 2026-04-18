import Foundation
#if canImport(UIKit)
import UIKit
#endif

/// HTTP client for the ForgeCommunicator mobile API (`/mobile/v1/`).
actor APIClient {
    static let shared = APIClient()

    private var baseURL: URL

    private init() {
        if let saved = UserDefaults.standard.string(forKey: "serverURL"),
           let base = URL(string: saved) {
            baseURL = base.appendingPathComponent("mobile/v1")
        } else {
            baseURL = URL(string: "https://comms.buildly.io/mobile/v1")!
        }
    }

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let str = try container.decode(String.self)
            // Try ISO 8601 with fractional seconds first
            if let date = ISO8601DateFormatter.withFractionalSeconds.date(from: str) { return date }
            if let date = ISO8601DateFormatter.standard.date(from: str) { return date }
            throw DecodingError.dataCorrupted(
                .init(codingPath: decoder.codingPath, debugDescription: "Cannot decode date: \(str)")
            )
        }
        return d
    }()

    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    private let session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        return URLSession(configuration: config)
    }()

    /// Update the base URL (e.g. from user settings).
    func setBaseURL(_ url: URL) {
        baseURL = url
    }

    // MARK: - Generic request

    private func request<T: Decodable>(
        _ method: String,
        path: String,
        body: (any Encodable)? = nil,
        query: [String: String] = [:]
    ) async throws -> T {
        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: true)!
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var req = URLRequest(url: components.url!)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Accept")

        if let token = KeychainService.loadToken() {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try encoder.encode(body)
        }

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw APIError.unknown
        }

        switch http.statusCode {
        case 200...299:
            return try decoder.decode(T.self, from: data)
        case 401:
            throw APIError.unauthorized
        case 403:
            throw APIError.forbidden
        case 404:
            throw APIError.notFound
        case 409:
            throw APIError.conflict(detail(from: data))
        case 422:
            throw APIError.validation(detail(from: data))
        case 429:
            throw APIError.rateLimited
        default:
            throw APIError.server(http.statusCode, detail(from: data))
        }
    }

    /// Fire-and-forget request (204 No Content, etc.)
    private func requestVoid(
        _ method: String,
        path: String,
        body: (any Encodable)? = nil
    ) async throws {
        var req = URLRequest(url: baseURL.appendingPathComponent(path))
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Accept")

        if let token = KeychainService.loadToken() {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try encoder.encode(body)
        }

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw APIError.unknown }
        guard (200...299).contains(http.statusCode) else {
            if http.statusCode == 401 { throw APIError.unauthorized }
            throw APIError.server(http.statusCode, detail(from: data))
        }
    }

    private func detail(from data: Data) -> String {
        if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let detail = obj["detail"] as? String {
            return detail
        }
        return String(data: data, encoding: .utf8) ?? "Unknown error"
    }

    // MARK: - Auth

    func login(email: String, password: String) async throws -> AuthResponse {
        let body = LoginRequest(email: email, password: password, deviceName: deviceName)
        return try await request("POST", path: "auth/login", body: body)
    }

    func register(email: String, password: String, displayName: String) async throws -> AuthResponse {
        let body = RegisterRequest(email: email, password: password, displayName: displayName, deviceName: deviceName)
        return try await request("POST", path: "auth/register", body: body)
    }

    func logout() async throws {
        try await requestVoid("POST", path: "auth/logout")
    }

    // MARK: - Profile

    func me() async throws -> UserResponse {
        try await request("GET", path: "me")
    }

    func updateProfile(_ update: ProfileUpdate) async throws -> UserResponse {
        try await request("PATCH", path: "me", body: update)
    }

    // MARK: - OAuth

    struct OAuthStartResponse: Decodable {
        let authUrl: String
        let state: String

        enum CodingKeys: String, CodingKey {
            case authUrl = "auth_url"
            case state
        }
    }

    func oauthStart(provider: String) async throws -> OAuthStartResponse {
        try await request("GET", path: "auth/oauth/\(provider)/start")
    }

    func getUser(id: Int) async throws -> UserResponse {
        try await request("GET", path: "users/\(id)")
    }

    // MARK: - Workspaces

    func workspaces() async throws -> [WorkspaceResponse] {
        try await request("GET", path: "workspaces")
    }

    func workspaceMembers(workspaceId: Int) async throws -> [UserResponse] {
        try await request("GET", path: "workspaces/\(workspaceId)/members")
    }

    // MARK: - Channels

    func channels(workspaceId: Int) async throws -> [ChannelResponse] {
        try await request("GET", path: "workspaces/\(workspaceId)/channels")
    }

    // MARK: - Conversations (inbox)

    func conversations(includeChannels: Bool = false) async throws -> [ConversationPreview] {
        var query: [String: String] = [:]
        if includeChannels { query["include_channels"] = "true" }
        return try await request("GET", path: "conversations", query: query)
    }

    // MARK: - Messages

    func messages(
        workspaceId: Int,
        channelId: Int,
        before: Int? = nil,
        after: Int? = nil,
        limit: Int = 50
    ) async throws -> [MessageResponse] {
        var query: [String: String] = ["limit": "\(limit)"]
        if let before { query["before"] = "\(before)" }
        if let after { query["after"] = "\(after)" }
        return try await request("GET", path: "workspaces/\(workspaceId)/channels/\(channelId)/messages", query: query)
    }

    func sendMessage(
        workspaceId: Int,
        channelId: Int,
        body: String,
        parentId: Int? = nil
    ) async throws -> MessageResponse {
        let payload = SendMessageRequest(body: body, parentId: parentId)
        return try await request("POST", path: "workspaces/\(workspaceId)/channels/\(channelId)/messages", body: payload)
    }

    func thread(workspaceId: Int, channelId: Int, messageId: Int) async throws -> [MessageResponse] {
        try await request("GET", path: "workspaces/\(workspaceId)/channels/\(channelId)/messages/\(messageId)/thread")
    }

    func markRead(workspaceId: Int, channelId: Int) async throws {
        try await requestVoid("POST", path: "workspaces/\(workspaceId)/channels/\(channelId)/read")
    }

    func createDM(workspaceId: Int, userIds: [Int]) async throws -> ChannelResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("workspaces/\(workspaceId)/dm"), resolvingAgainstBaseURL: true)!
        components.queryItems = userIds.map { URLQueryItem(name: "user_ids", value: "\($0)") }
        var req = URLRequest(url: components.url!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token = KeychainService.loadToken() {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw APIError.unknown
        }
        return try decoder.decode(ChannelResponse.self, from: data)
    }

    // MARK: - Integrations

    func integrationStatus() async throws -> IntegrationStatusResponse {
        try await request("GET", path: "integrations/status")
    }

    func slackAuthURL() async throws -> IntegrationAuthURLResponse {
        try await request("GET", path: "integrations/slack/auth-url")
    }

    func discordAuthURL() async throws -> IntegrationAuthURLResponse {
        try await request("GET", path: "integrations/discord/auth-url")
    }

    func disconnectSlack() async throws {
        try await requestVoid("POST", path: "integrations/slack/disconnect")
    }

    func syncSlackChannels(workspaceId: Int) async throws -> SlackSyncResult {
        try await request("POST", path: "integrations/slack/sync", query: ["workspace_id": "\(workspaceId)"])
    }

    func disconnectDiscord() async throws {
        try await requestVoid("POST", path: "integrations/discord/disconnect")
    }

    // MARK: - Helpers

    private var deviceName: String {
        #if canImport(UIKit)
        return UIDevice.current.name
        #else
        return Host.current().localizedName ?? "Mac"
        #endif
    }
}

// MARK: - Error types

enum APIError: LocalizedError {
    case unauthorized
    case forbidden
    case notFound
    case conflict(String)
    case validation(String)
    case rateLimited
    case server(Int, String)
    case unknown

    var errorDescription: String? {
        switch self {
        case .unauthorized: return "Session expired. Please log in again."
        case .forbidden: return "You don't have permission."
        case .notFound: return "Not found."
        case .conflict(let msg): return msg
        case .validation(let msg): return msg
        case .rateLimited: return "Too many requests. Please wait."
        case .server(_, let msg): return msg
        case .unknown: return "Something went wrong."
        }
    }
}

// MARK: - ISO 8601 formatters

extension ISO8601DateFormatter {
    static let withFractionalSeconds: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    static let standard: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()
}
