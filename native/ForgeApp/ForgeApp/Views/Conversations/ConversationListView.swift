import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

struct ConversationListView: View {
    @StateObject private var vm = ConversationListViewModel()
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var notificationService: NotificationService
    @State private var slackConnected = false
    @State private var discordConnected = false

    private let api = APIClient.shared
    private let webBaseURL = "https://comms.buildly.io"

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading {
                    ProgressView("Loading…")
                        .tint(ForgeTheme.primary)
                        .frame(maxHeight: .infinity)
                } else if let error = vm.error {
                    ContentUnavailableView {
                        Label("Error", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("Retry") { Task { await vm.load() } }
                            .tint(ForgeTheme.primary)
                    }
                } else if vm.conversations.isEmpty {
                    ContentUnavailableView(
                        "No conversations yet",
                        systemImage: "message",
                        description: Text("Start a conversation to get going.")
                    )
                } else {
                    conversationSections
                }
            }
            .background(ForgeTheme.dark900)
            .forgeLogoToolbar(title: "Messages")
            .navigationDestination(for: ConversationPreview.self) { conv in
                ChatView(
                    channelId: conv.channelId,
                    workspaceId: conv.workspaceId,
                    title: conv.name
                )
            }
        }
        .task {
            await vm.load()
            await loadIntegrationStatus()
        }
        .onChange(of: vm.conversations) { _, convos in
            let total = convos.reduce(0) { $0 + $1.unreadCount }
            notificationService.unreadCount = total
        }
    }

    // MARK: - Sectioned List

    private var conversationSections: some View {
        List {
            // 1. DMs
            if !dmConversations.isEmpty {
                Section {
                    ForEach(dmConversations) { conv in
                        conversationLink(conv)
                    }
                } header: {
                    sectionHeader("Direct Messages", icon: "message.fill", count: dmUnreadCount)
                }
            }

            // 2. @Mentions
            if !mentionConversations.isEmpty {
                Section {
                    ForEach(mentionConversations) { conv in
                        conversationLink(conv)
                    }
                } header: {
                    sectionHeader("@Mentions", icon: "at", count: mentionConversations.count)
                }
            }

            // 3. Channels (non-DM, no unread — i.e. remaining channels)
            if !channelConversations.isEmpty {
                Section {
                    ForEach(channelConversations) { conv in
                        conversationLink(conv)
                    }
                } header: {
                    sectionHeader("Channels", icon: "number", count: 0)
                }
            }

            // 4. Slack (only if connected)
            if slackConnected, !slackConversations.isEmpty {
                Section {
                    ForEach(slackConversations) { conv in
                        conversationLink(conv)
                    }
                } header: {
                    sectionHeader("Slack", icon: "number.square.fill", count: slackUnreadCount, color: .purple)
                }
            }

            // 5. Discord (only if connected)
            if discordConnected, !discordConversations.isEmpty {
                Section {
                    ForEach(discordConversations) { conv in
                        conversationLink(conv)
                    }
                } header: {
                    sectionHeader("Discord", icon: "gamecontroller.fill", count: discordUnreadCount, color: .indigo)
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .refreshable {
            await vm.load()
            await loadIntegrationStatus()
        }
    }

    // MARK: - Row builder

    private func conversationLink(_ conv: ConversationPreview) -> some View {
        NavigationLink(value: conv) {
            ConversationRow(
                conversation: conv,
                currentUserId: authVM.currentUser?.id,
                webBaseURL: webBaseURL
            )
        }
        .listRowBackground(ForgeTheme.dark900)
        .swipeActions(edge: .trailing) {
            Button {
                openInWeb(conv)
            } label: {
                Label("Open Web", systemImage: "safari")
            }
            .tint(ForgeTheme.primary)
        }
    }

    // MARK: - Section header

    private func sectionHeader(_ title: String, icon: String, count: Int, color: Color = ForgeTheme.primary) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .foregroundStyle(color)
                .font(.caption)
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(ForgeTheme.textSecondary)
            Spacer()
            if count > 0 {
                Text("\(count)")
                    .font(.caption2.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(color, in: Capsule())
            }
        }
    }

    // MARK: - Filtered data

    private var dmConversations: [ConversationPreview] {
        vm.conversations.filter { $0.isDm && $0.lastMessage?.externalSource == nil }
    }

    private var dmUnreadCount: Int {
        dmConversations.reduce(0) { $0 + $1.unreadCount }
    }

    private var mentionConversations: [ConversationPreview] {
        vm.conversations.filter { !$0.isDm && $0.unreadCount > 0 && $0.lastMessage?.externalSource == nil }
    }

    private var channelConversations: [ConversationPreview] {
        vm.conversations.filter { !$0.isDm && $0.unreadCount == 0 && $0.lastMessage?.externalSource == nil }
    }

    private var slackConversations: [ConversationPreview] {
        vm.conversations.filter { $0.lastMessage?.externalSource == "slack" }
    }

    private var slackUnreadCount: Int {
        slackConversations.reduce(0) { $0 + $1.unreadCount }
    }

    private var discordConversations: [ConversationPreview] {
        vm.conversations.filter { $0.lastMessage?.externalSource == "discord" }
    }

    private var discordUnreadCount: Int {
        discordConversations.reduce(0) { $0 + $1.unreadCount }
    }

    // MARK: - Actions

    private func loadIntegrationStatus() async {
        do {
            let status = try await api.integrationStatus()
            slackConnected = status.slackConnected
            discordConnected = status.discordConnected
        } catch {
            // Silently ignore — sections just won't show
        }
    }

    private func openInWeb(_ conv: ConversationPreview) {
        let urlString = "\(webBaseURL)/workspaces/\(conv.workspaceId)/channels/\(conv.channelId)"
        guard let url = URL(string: urlString) else { return }
        #if canImport(UIKit)
        UIApplication.shared.open(url)
        #elseif canImport(AppKit)
        NSWorkspace.shared.open(url)
        #endif
    }
}

// MARK: - Row

struct ConversationRow: View {
    let conversation: ConversationPreview
    let currentUserId: Int?
    var webBaseURL: String = "https://comms.buildly.io"

    var body: some View {
        HStack(spacing: 12) {
            // Source indicator for bridged messages
            if let source = conversation.lastMessage?.externalSource {
                sourceIcon(source)
            }

            // Avatar
            AvatarView(user: otherMember, size: 48)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(displayName)
                        .font(.headline)
                        .lineLimit(1)
                    Spacer()
                    if let date = conversation.lastMessage?.createdAt {
                        Text(date, style: .relative)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                HStack {
                    if let msg = conversation.lastMessage {
                        Text(msg.body)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                    Spacer()

                    // Open in web button
                    Button {
                        let urlString = "\(webBaseURL)/workspaces/\(conversation.workspaceId)/channels/\(conversation.channelId)"
                        if let url = URL(string: urlString) {
                            #if canImport(UIKit)
                            UIApplication.shared.open(url)
                            #elseif canImport(AppKit)
                            NSWorkspace.shared.open(url)
                            #endif
                        }
                    } label: {
                        Image(systemName: "arrow.up.right.square")
                            .font(.caption)
                            .foregroundStyle(ForgeTheme.textMuted)
                    }
                    .buttonStyle(.plain)

                    if conversation.unreadCount > 0 {
                        Text("\(conversation.unreadCount)")
                            .font(.caption2.bold())
                            .foregroundStyle(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(ForgeTheme.primary, in: Capsule())
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private func sourceIcon(_ source: String) -> some View {
        switch source {
        case "slack":
            Image(systemName: "number.square.fill")
                .foregroundStyle(.purple)
                .font(.caption)
        case "discord":
            Image(systemName: "gamecontroller.fill")
                .foregroundStyle(.indigo)
                .font(.caption)
        default:
            EmptyView()
        }
    }

    private var otherMember: UserResponse? {
        conversation.members.first { $0.id != currentUserId }
    }

    private var displayName: String {
        if conversation.isDm, let other = otherMember {
            return other.displayName
        }
        return conversation.name
    }
}

// MARK: - Avatar

struct AvatarView: View {
    let user: UserResponse?
    let size: CGFloat

    var body: some View {
        if let url = user?.avatarUrl.flatMap({ URL(string: $0) }) {
            AsyncImage(url: url) { image in
                image.resizable().scaledToFill()
            } placeholder: {
                initialsView
            }
            .frame(width: size, height: size)
            .clipShape(Circle())
        } else {
            initialsView
        }
    }

    private var initialsView: some View {
        Circle()
            .fill(
                LinearGradient(
                    colors: [ForgeTheme.primary.opacity(0.3), ForgeTheme.accent.opacity(0.2)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .frame(width: size, height: size)
            .overlay {
                Text(user?.initials ?? "?")
                    .font(.system(size: size * 0.38, weight: .semibold))
                    .foregroundStyle(ForgeTheme.primary)
            }
    }
}
