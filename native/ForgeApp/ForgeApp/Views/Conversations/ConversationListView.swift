import SwiftUI

struct ConversationListView: View {
    @StateObject private var vm = ConversationListViewModel()
    @EnvironmentObject var authVM: AuthViewModel

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading {
                    ProgressView("Loading…")
                } else if let error = vm.error {
                    ContentUnavailableView {
                        Label("Error", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("Retry") { Task { await vm.load() } }
                    }
                } else if vm.conversations.isEmpty {
                    ContentUnavailableView("No conversations yet",
                        systemImage: "message",
                        description: Text("Start a direct message to get going."))
                } else {
                    List(vm.conversations) { conv in
                        NavigationLink(value: conv) {
                            ConversationRow(conversation: conv, currentUserId: authVM.currentUser?.id)
                        }
                    }
                    .listStyle(.plain)
                    .refreshable { await vm.load() }
                }
            }
            .navigationTitle("Messages")
            .navigationDestination(for: ConversationPreview.self) { conv in
                ChatView(
                    channelId: conv.channelId,
                    workspaceId: conv.workspaceId,
                    title: conv.name
                )
            }
        }
        .task { await vm.load() }
    }
}

// MARK: - Row

struct ConversationRow: View {
    let conversation: ConversationPreview
    let currentUserId: Int?

    var body: some View {
        HStack(spacing: 12) {
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
                    if conversation.unreadCount > 0 {
                        Text("\(conversation.unreadCount)")
                            .font(.caption2.bold())
                            .foregroundStyle(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(.blue, in: Capsule())
                    }
                }
            }
        }
        .padding(.vertical, 4)
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
            .fill(.blue.opacity(0.15))
            .frame(width: size, height: size)
            .overlay {
                Text(user?.initials ?? "?")
                    .font(.system(size: size * 0.38, weight: .semibold))
                    .foregroundStyle(.blue)
            }
    }
}
