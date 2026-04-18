import Foundation

// MARK: - User

struct UserResponse: Codable, Identifiable, Hashable {
    let id: Int
    let email: String
    let displayName: String
    let bio: String?
    let title: String?
    let phone: String?
    let avatarUrl: String?
    let status: String
    let statusMessage: String?
    let githubUrl: String?
    let linkedinUrl: String?
    let twitterUrl: String?
    let websiteUrl: String?
    let lastSeenAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, email, bio, title, phone, status
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
        case statusMessage = "status_message"
        case githubUrl = "github_url"
        case linkedinUrl = "linkedin_url"
        case twitterUrl = "twitter_url"
        case websiteUrl = "website_url"
        case lastSeenAt = "last_seen_at"
    }

    static func == (lhs: UserResponse, rhs: UserResponse) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }

    var initials: String {
        let parts = displayName.split(separator: " ")
        if parts.count >= 2 {
            return String(parts[0].prefix(1) + parts[1].prefix(1)).uppercased()
        }
        return String(displayName.prefix(2)).uppercased()
    }

    var isOnline: Bool { status == "active" }
}

// MARK: - Auth

struct LoginRequest: Encodable {
    let email: String
    let password: String
    let deviceName: String?

    enum CodingKeys: String, CodingKey {
        case email, password
        case deviceName = "device_name"
    }
}

struct RegisterRequest: Encodable {
    let email: String
    let password: String
    let displayName: String
    let deviceName: String?

    enum CodingKeys: String, CodingKey {
        case email, password
        case displayName = "display_name"
        case deviceName = "device_name"
    }
}

struct AuthResponse: Codable {
    let token: String
    let user: UserResponse
}

// MARK: - Workspace

struct WorkspaceResponse: Codable, Identifiable, Hashable {
    let id: Int
    let name: String
    let slug: String
    let description: String?
    let iconUrl: String?
    let memberCount: Int
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, name, slug, description
        case iconUrl = "icon_url"
        case memberCount = "member_count"
        case createdAt = "created_at"
    }

    static func == (lhs: WorkspaceResponse, rhs: WorkspaceResponse) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}

// MARK: - Channel

struct ChannelResponse: Codable, Identifiable, Hashable {
    let id: Int
    let workspaceId: Int
    let name: String
    let displayName: String
    let description: String?
    let topic: String?
    let isPrivate: Bool
    let isDm: Bool
    let isArchived: Bool
    var unreadCount: Int
    let lastMessageAt: Date?
    let members: [UserResponse]?

    enum CodingKeys: String, CodingKey {
        case id, name, description, topic, members
        case workspaceId = "workspace_id"
        case displayName = "display_name"
        case isPrivate = "is_private"
        case isDm = "is_dm"
        case isArchived = "is_archived"
        case unreadCount = "unread_count"
        case lastMessageAt = "last_message_at"
    }

    static func == (lhs: ChannelResponse, rhs: ChannelResponse) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}

// MARK: - Message

struct MessageResponse: Codable, Identifiable, Hashable {
    let id: Int
    let channelId: Int
    let userId: Int?
    let body: String
    let parentId: Int?
    let threadReplyCount: Int
    let createdAt: Date
    let editedAt: Date?
    let isEdited: Bool
    let externalSource: String?
    let externalAuthorName: String?
    let author: UserResponse?

    enum CodingKeys: String, CodingKey {
        case id, body, author
        case channelId = "channel_id"
        case userId = "user_id"
        case parentId = "parent_id"
        case threadReplyCount = "thread_reply_count"
        case createdAt = "created_at"
        case editedAt = "edited_at"
        case isEdited = "is_edited"
        case externalSource = "external_source"
        case externalAuthorName = "external_author_name"
    }

    static func == (lhs: MessageResponse, rhs: MessageResponse) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }

    var authorName: String {
        author?.displayName ?? externalAuthorName ?? "Unknown"
    }
}

// MARK: - Conversation Preview

struct ConversationPreview: Codable, Identifiable, Hashable {
    var id: Int { channelId }
    let channelId: Int
    let workspaceId: Int
    let workspaceName: String
    let name: String
    let isDm: Bool
    let lastMessage: MessageResponse?
    var unreadCount: Int
    let members: [UserResponse]
    let bridgedPlatform: String?  // "slack" or "discord" if bridged

    enum CodingKeys: String, CodingKey {
        case name, members
        case channelId = "channel_id"
        case workspaceId = "workspace_id"
        case workspaceName = "workspace_name"
        case isDm = "is_dm"
        case lastMessage = "last_message"
        case unreadCount = "unread_count"
        case bridgedPlatform = "bridged_platform"
    }

    static func == (lhs: ConversationPreview, rhs: ConversationPreview) -> Bool { lhs.channelId == rhs.channelId }
    func hash(into hasher: inout Hasher) { hasher.combine(channelId) }
}

// MARK: - Send

struct SendMessageRequest: Encodable {
    let body: String
    let parentId: Int?

    enum CodingKeys: String, CodingKey {
        case body
        case parentId = "parent_id"
    }
}

// MARK: - Integrations

struct IntegrationStatusResponse: Codable {
    let slackConnected: Bool
    let slackWorkspace: String?
    let discordConnected: Bool
    let discordServer: String?

    enum CodingKeys: String, CodingKey {
        case slackConnected = "slack_connected"
        case slackWorkspace = "slack_workspace"
        case discordConnected = "discord_connected"
        case discordServer = "discord_server"
    }
}

struct IntegrationAuthURLResponse: Codable {
    let url: String
}
