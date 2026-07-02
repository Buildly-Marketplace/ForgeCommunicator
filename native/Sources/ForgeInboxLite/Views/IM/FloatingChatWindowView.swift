import SwiftUI

// MARK: - FloatingChatWindowView

struct FloatingChatWindowView: View {
    let conversation: CommunicatorConversation
    @ObservedObject var store: NativeCommunicatorStore

    @State private var draft = ""
    @State private var isLoadingMessages = false

    var body: some View {
        VStack(spacing: 0) {
            titleBar
            messagesArea
            composer
        }
        .background(ForgeTheme.dark900)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear {
            if store.messages.isEmpty {
                Task { await loadMessages() }
            }
            Task { try? await markRead() }
        }
    }

    // MARK: - Title Bar

    private var titleBar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                conversationAvatar(size: 28)

                Text(conversation.name)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(ForgeTheme.silver)
                    .lineLimit(1)

                if let platform = conversation.bridgedPlatform {
                    platformPill(platform)
                }

                Spacer()

                if conversation.unreadCount > 0 {
                    unreadBadge(count: conversation.unreadCount)
                }

                markReadButton
            }
            .padding(.horizontal, 12)
            .frame(height: 44)

            Divider()
                .background(ForgeTheme.glassBorder)
                .frame(height: 1)
        }
        .background(ForgeTheme.dark950)
    }

    private func platformPill(_ platform: String) -> some View {
        Text(platform.capitalized)
            .font(.system(size: 10, weight: .semibold))
            .foregroundStyle(ForgeTheme.primary)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(ForgeTheme.primary.opacity(0.15))
            .clipShape(Capsule())
    }

    private func unreadBadge(count: Int) -> some View {
        Text("\(min(count, 99))")
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(ForgeTheme.dark950)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(ForgeTheme.primary)
            .clipShape(Capsule())
    }

    private var markReadButton: some View {
        Button {
            Task { try? await markRead() }
        } label: {
            Image(systemName: "checkmark.circle")
                .font(.system(size: 14))
                .foregroundStyle(ForgeTheme.silver.opacity(0.5))
        }
        .buttonStyle(.plain)
        .help("Mark as read")
    }

    // MARK: - Messages Area

    private var messagesArea: some View {
        ScrollViewReader { proxy in
            ScrollView {
                if store.messages.isEmpty {
                    emptyState
                } else {
                    LazyVStack(spacing: 2) {
                        ForEach(store.messages) { message in
                            IMMessageRow(
                                message: message,
                                currentUserDisplayName: store.currentUserDisplayName
                            )
                            .id(message.id)
                        }

                        // Scroll anchor
                        Color.clear
                            .frame(height: 1)
                            .id("bottom")
                    }
                    .padding(.vertical, 8)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .onAppear {
                scrollToBottom(proxy: proxy, animated: false)
            }
            .onChange(of: store.messages.count) { _ in
                scrollToBottom(proxy: proxy, animated: true)
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 32))
                .foregroundStyle(ForgeTheme.silver.opacity(0.3))
            Text("No messages yet")
                .font(.system(size: 13))
                .foregroundStyle(ForgeTheme.silver.opacity(0.4))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.top, 60)
    }

    private func scrollToBottom(proxy: ScrollViewProxy, animated: Bool) {
        if animated {
            withAnimation(.easeOut(duration: 0.2)) {
                proxy.scrollTo("bottom", anchor: .bottom)
            }
        } else {
            proxy.scrollTo("bottom", anchor: .bottom)
        }
    }

    // MARK: - Composer

    private var composer: some View {
        VStack(spacing: 0) {
            Divider()
                .background(ForgeTheme.glassBorder)
                .frame(height: 1)

            HStack(alignment: .bottom, spacing: 8) {
                ZStack(alignment: .topLeading) {
                    if draft.isEmpty {
                        Text("Message \(conversation.name)...")
                            .font(.system(size: 13))
                            .foregroundStyle(ForgeTheme.silver.opacity(0.35))
                            .padding(.top, 8)
                            .padding(.leading, 4)
                            .allowsHitTesting(false)
                    }

                    TextEditor(text: $draft)
                        .font(.system(size: 13))
                        .foregroundStyle(ForgeTheme.silver)
                        .scrollContentBackground(.hidden)
                        .background(.clear)
                        .frame(minHeight: 20, maxHeight: 88)
                        .onSubmit {
                            sendMessage()
                        }
                }

                Button(action: sendMessage) {
                    Image(systemName: "arrow.up")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(ForgeTheme.dark950)
                        .frame(width: 32, height: 32)
                        .background(
                            draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                ? ForgeTheme.primary.opacity(0.35)
                                : ForgeTheme.primary
                        )
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)
                .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .keyboardShortcut(.return, modifiers: .command)
            }
            .padding(10)
        }
        .background(ForgeTheme.dark950)
    }

    // MARK: - Actions

    private func sendMessage() {
        let body = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return }

        draft = ""
        store.draft = body

        Task {
            await store.sendDraftMessage()
        }
    }

    private func loadMessages() async {
        isLoadingMessages = true
        defer { isLoadingMessages = false }
        await store.loadMessages()
    }

    private func markRead() async throws {
        try await store.markRead()
    }

    // MARK: - Helpers

    private func conversationAvatar(size: CGFloat) -> some View {
        let initials = conversation.name
            .split(separator: " ")
            .prefix(2)
            .compactMap { $0.first.map(String.init) }
            .joined()
            .uppercased()

        return Text(initials.isEmpty ? "#" : initials)
            .font(.system(size: size * 0.38, weight: .semibold))
            .foregroundStyle(ForgeTheme.silver)
            .frame(width: size, height: size)
            .background(ForgeTheme.dark700)
            .clipShape(Circle())
    }
}

// MARK: - IMMessageRow

private struct IMMessageRow: View {
    let message: CommunicatorMessage
    let currentUserDisplayName: String?

    @State private var isHovered = false

    private var isOwn: Bool {
        guard let displayName = currentUserDisplayName,
              let authorName = message.author?.displayName
        else { return false }
        return authorName == displayName
    }

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if isOwn { Spacer(minLength: 32) }

            if !isOwn {
                authorAvatar
            }

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(message.author?.displayName ?? "Unknown")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(ForgeTheme.white)

                    Text(message.createdAt, format: timestampFormat)
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                }

                Text(message.body)
                    .font(.system(size: 13))
                    .foregroundStyle(ForgeTheme.silver)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if isOwn {
                authorAvatar
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 3)
        .background(rowBackground)
        .contentShape(Rectangle())
        .onHover { isHovered = $0 }
    }

    private var rowBackground: some View {
        Group {
            if isOwn {
                ForgeTheme.primary.opacity(0.08)
            } else if isHovered {
                ForgeTheme.dark800.opacity(0.5)
            } else {
                Color.clear
            }
        }
    }

    private var authorAvatar: some View {
        let name = message.author?.displayName ?? ""
        let initials = name
            .split(separator: " ")
            .prefix(2)
            .compactMap { $0.first.map(String.init) }
            .joined()
            .uppercased()

        if let avatarURLString = message.author?.avatarURL,
           let avatarURL = URL(string: avatarURLString) {
            return AnyView(
                AsyncImage(url: avatarURL) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().scaledToFill()
                    default:
                        initialsView(initials: initials.isEmpty ? "?" : initials)
                    }
                }
                .frame(width: 28, height: 28)
                .clipShape(Circle())
            )
        } else {
            return AnyView(
                initialsView(initials: initials.isEmpty ? "?" : initials)
                    .frame(width: 28, height: 28)
                    .clipShape(Circle())
            )
        }
    }

    private func initialsView(initials: String) -> some View {
        Text(initials)
            .font(.system(size: 10, weight: .semibold))
            .foregroundStyle(ForgeTheme.silver)
            .frame(width: 28, height: 28)
            .background(ForgeTheme.dark700)
    }

    private var timestampFormat: Date.FormatStyle {
        let now = Date()
        let calendar = Calendar.current
        if calendar.isDateInToday(message.createdAt) {
            return .dateTime.hour().minute()
        } else {
            return .dateTime.month(.abbreviated).day()
        }
    }
}
