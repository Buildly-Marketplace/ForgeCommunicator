import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

// MARK: - Filter enum

enum InboxFilter: String, CaseIterable, Identifiable {
    case dms
    case mentions
    case channels

    var id: String { rawValue }

    var label: String {
        switch self {
        case .dms: return "DMs"
        case .mentions: return "@Mentions"
        case .channels: return "Channels"
        }
    }
}

struct ConversationListView: View {
    @StateObject private var vm = ConversationListViewModel()
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var notificationService: NotificationService
    @State private var filter: InboxFilter = .dms
    @State private var slackConnected = false
    @State private var discordConnected = false
    @State private var workspaces: [WorkspaceResponse] = []
    @State private var selectedWorkspaceId: Int? // nil = All

    private let api = APIClient.shared
    private let webBaseURL = "https://comms.buildly.io"

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Sub-navigation: workspace dropdown + filter picker
                HStack(spacing: 8) {
                    if workspaces.count > 1 {
                        Menu {
                            Button {
                                selectedWorkspaceId = nil
                            } label: {
                                if selectedWorkspaceId == nil {
                                    Label("All Workspaces", systemImage: "checkmark")
                                } else {
                                    Text("All Workspaces")
                                }
                            }
                            ForEach(workspaces) { ws in
                                Button {
                                    selectedWorkspaceId = ws.id
                                } label: {
                                    if selectedWorkspaceId == ws.id {
                                        Label(ws.name, systemImage: "checkmark")
                                    } else {
                                        Text(ws.name)
                                    }
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Text(selectedWorkspaceName)
                                    .font(.subheadline.weight(.medium))
                                Image(systemName: "chevron.down")
                                    .font(.caption2.weight(.semibold))
                            }
                            .foregroundStyle(.white)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(ForgeTheme.dark700, in: Capsule())
                        }
                    }

                    Picker("Filter", selection: $filter) {
                        ForEach(InboxFilter.allCases) { f in
                            Text(f.label).tag(f)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

                // Content
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
                    } else {
                        conversationContent
                    }
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
            await loadWorkspaces()
            await loadIntegrationStatus()
        }
        .onChange(of: vm.conversations) { _, convos in
            let total = convos.reduce(0) { $0 + $1.unreadCount }
            notificationService.unreadCount = total
        }
    }

    // MARK: - Workspace dropdown helper

    private var selectedWorkspaceName: String {
        if let wsId = selectedWorkspaceId,
           let ws = workspaces.first(where: { $0.id == wsId }) {
            return ws.name
        }
        return "All"
    }

    // MARK: - Content

    private var conversationContent: some View {
        Group {
            if filteredConversations.isEmpty && slackSectionConversations.isEmpty && discordSectionConversations.isEmpty {
                ContentUnavailableView(
                    emptyTitle,
                    systemImage: emptyIcon,
                    description: Text(emptyDescription)
                )
            } else {
                List {
                    // Main filtered section
                    if !filteredConversations.isEmpty {
                        Section {
                            ForEach(filteredConversations) { conv in
                                conversationLink(conv)
                            }
                        } header: {
                            sectionHeader(filter.label, icon: filterIcon, count: filteredUnreadCount)
                        }
                    }

                    // Slack section (always shown when connected & has data, regardless of filter)
                    if slackConnected, !slackSectionConversations.isEmpty {
                        Section {
                            ForEach(slackSectionConversations) { conv in
                                conversationLink(conv)
                            }
                        } header: {
                            sectionHeader("Slack", icon: "number.square.fill", count: slackUnreadCount, color: .purple)
                        }
                    }

                    // Discord section
                    if discordConnected, !discordSectionConversations.isEmpty {
                        Section {
                            ForEach(discordSectionConversations) { conv in
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

    // MARK: - Workspace-filtered base

    /// All conversations after workspace filter (before category filter)
    private var workspaceFiltered: [ConversationPreview] {
        if let wsId = selectedWorkspaceId {
            return vm.conversations.filter { $0.workspaceId == wsId }
        }
        return vm.conversations
    }

    /// Non-bridged conversations (native Forge messages)
    private var nativeConversations: [ConversationPreview] {
        workspaceFiltered.filter { $0.bridgedPlatform == nil }
    }

    // MARK: - Category-filtered data

    private var filteredConversations: [ConversationPreview] {
        switch filter {
        case .dms:
            return nativeConversations.filter { $0.isDm }
        case .mentions:
            return nativeConversations.filter { !$0.isDm && $0.unreadCount > 0 }
        case .channels:
            return nativeConversations.filter { !$0.isDm }
        }
    }

    private var filteredUnreadCount: Int {
        filteredConversations.reduce(0) { $0 + $1.unreadCount }
    }

    private var filterIcon: String {
        switch filter {
        case .dms: return "message.fill"
        case .mentions: return "at"
        case .channels: return "number"
        }
    }

    private var slackSectionConversations: [ConversationPreview] {
        workspaceFiltered.filter { $0.bridgedPlatform == "slack" }
    }

    private var slackUnreadCount: Int {
        slackSectionConversations.reduce(0) { $0 + $1.unreadCount }
    }

    private var discordSectionConversations: [ConversationPreview] {
        workspaceFiltered.filter { $0.bridgedPlatform == "discord" }
    }

    private var discordUnreadCount: Int {
        discordSectionConversations.reduce(0) { $0 + $1.unreadCount }
    }

    // MARK: - Empty state

    private var emptyTitle: String {
        switch filter {
        case .dms: return "No direct messages"
        case .mentions: return "No mentions yet"
        case .channels: return "No channels"
        }
    }

    private var emptyIcon: String {
        switch filter {
        case .dms: return "message"
        case .mentions: return "at"
        case .channels: return "number"
        }
    }

    private var emptyDescription: String {
        switch filter {
        case .dms: return "Start a DM to get going."
        case .mentions: return "You'll see threads where you're @mentioned."
        case .channels: return "Join a channel to see it here."
        }
    }

    // MARK: - Actions

    private func loadWorkspaces() async {
        do {
            workspaces = try await api.workspaces()
        } catch { /* silent */ }
    }

    private func loadIntegrationStatus() async {
        do {
            let status = try await api.integrationStatus()
            slackConnected = status.slackConnected
            discordConnected = status.discordConnected
        } catch { /* silent */ }
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
