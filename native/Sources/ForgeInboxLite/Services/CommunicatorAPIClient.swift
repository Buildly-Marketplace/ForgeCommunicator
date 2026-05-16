import Foundation

struct CommunicatorAPIClient {
    enum APIError: LocalizedError {
        case invalidServerURL
        case invalidResponse
        case unauthorized
        case serverError(status: Int, message: String)

        var errorDescription: String? {
            switch self {
            case .invalidServerURL:
                return "Invalid server URL."
            case .invalidResponse:
                return "Invalid server response."
            case .unauthorized:
                return "Authentication failed."
            case let .serverError(status, message):
                return "Server error (\(status)): \(message)"
            }
        }
    }

    private let baseURL: URL
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(serverURL: String) throws {
        var value = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if !value.hasPrefix("http://") && !value.hasPrefix("https://") {
            value = "https://\(value)"
        }
        guard let url = URL(string: value) else {
            throw APIError.invalidServerURL
        }

        self.baseURL = url

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        self.decoder = decoder

        self.encoder = JSONEncoder()
    }

    func login(email: String, password: String) async throws -> CommunicatorAuthResponse {
        var request = URLRequest(url: endpoint("/mobile/v1/auth/login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: String] = [
            "email": email,
            "password": password,
            "device_name": "ForgeCommunicator-macOS"
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        return try await perform(request, as: CommunicatorAuthResponse.self)
    }

    func listConversations(token: String, includeChannels: Bool = true) async throws -> [CommunicatorConversation] {
        var components = URLComponents(url: endpoint("/mobile/v1/conversations"), resolvingAgainstBaseURL: false)
        if includeChannels {
            components?.queryItems = [URLQueryItem(name: "include_channels", value: "true")]
        }

        var request = URLRequest(url: components?.url ?? endpoint("/mobile/v1/conversations"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        return try await perform(request, as: [CommunicatorConversation].self)
    }

    func listMessages(token: String, workspaceID: Int, channelID: Int) async throws -> [CommunicatorMessage] {
        var request = URLRequest(url: endpoint("/mobile/v1/workspaces/\(workspaceID)/channels/\(channelID)/messages"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        return try await perform(request, as: [CommunicatorMessage].self)
    }

    func sendMessage(token: String, workspaceID: Int, channelID: Int, body: String) async throws -> CommunicatorMessage {
        var request = URLRequest(url: endpoint("/mobile/v1/workspaces/\(workspaceID)/channels/\(channelID)/messages"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try encoder.encode(CommunicatorSendMessageRequest(body: body))

        return try await perform(request, as: CommunicatorMessage.self)
    }

    func markRead(token: String, workspaceID: Int, channelID: Int) async throws {
        var request = URLRequest(url: endpoint("/mobile/v1/workspaces/\(workspaceID)/channels/\(channelID)/read"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        _ = try await performRaw(request)
    }

    private func endpoint(_ path: String) -> URL {
        if path.hasPrefix("/") {
            return baseURL.appending(path: String(path.dropFirst()))
        }
        return baseURL.appending(path: path)
    }

    private func performRaw(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        switch http.statusCode {
        case 200 ... 299:
            return (data, http)
        case 401:
            throw APIError.unauthorized
        default:
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.serverError(status: http.statusCode, message: message)
        }
    }

    private func perform<T: Decodable>(_ request: URLRequest, as type: T.Type) async throws -> T {
        let (data, _) = try await performRaw(request)
        return try decoder.decode(type, from: data)
    }
}
