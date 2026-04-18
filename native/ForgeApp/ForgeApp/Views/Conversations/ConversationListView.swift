import SwiftUI

struct ConversationListView: View {
    @StateObject private var vm = ConversationListViewModel()
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var notificationService: NotificationService
    @State private var filter: InboxFilter = .dms

    private let webBaseURL = "https://comms.buildly.io"

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Filter picker
                Picker("Filter", selection: $filter) {
                    ForEach(InboxFilter.allCases) { f in
                        Text(f.label).tag(f)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

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
                    } else if filteredConversations.isEmpty {
                        ContentUnavailableView(
                            emptyTitle,
                            systemImage: emptyIcon,
                            description: Text(emptyDescription)
                        )
                    } else {
                        List(filteredConversations) { conv in
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
                        .listStyle(.plain)
                        .scrollContentBackground(.hidden)
                        .refreshable { await vm.load() }
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
        .task { await vm.load() }
        .onChange(of: vm.conversations) { _, convos in
            let total = convos.reduce(0) { $0 + $1.unreadCount }
            notificationService.unreadCount = total
        }
    }

    private var filteredConversations: [ConversationPreview] {
        switch filter {
        case .dms:
            // Show all DMs including bridged Slack/Discord DMs
            return vm.conversations.filter { $0.isDm }
        case .mentions:
            // Show non-DM channels with unread (includes bridged channels with @mentions)
            return vm.conversations.filter { !$0.isDm && $0.unreadCount > 0 }
        case .bridged:
            // Show channels with external (Slack/Discord) messages
            return vm.conversations.filter {
                $0.lastMessage?.externalSource != nil
            }
        }
    }

    private var emptyTitle: String {
        switch filter {
        case .dms: return "No direct messages"
        case .mentions: return "No mentions yet"
        case .bridged: return "No Slack/Discord messages"
        }
    }

    private var emptyIcon: String {
        switch filter {
        case .dms: return "message"
        case .mentions: return "at"
        case .bridged: return "link.circle"
        }
    }

    private var emptyDescription: String {
        switch filter {
        case .dms: return "Start a DM to get going."
        case .mentions: return "You'll see threads where you're @mentioned."
        case .bridged: return "Connect Slack or Discord in Integrations to see bridged messages here."
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

// MARK: - Filter

enum InboxFilter: String, CaseIterable, Identifiable {
    case dms
    case mentions
    case bridged

    var id: String { rawValue }

    var label: String {
        switch self {
        case .dms: return "DMs"
        case .mentions: return "@Mentions"
        case .bridged: return "Slack/Discord"
        }
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
