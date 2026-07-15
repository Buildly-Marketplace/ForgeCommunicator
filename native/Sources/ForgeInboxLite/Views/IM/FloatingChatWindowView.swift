import SwiftUI
import AppKit

// MARK: - FloatingChatWindowView

struct FloatingChatWindowView: View {
    let conversation: CommunicatorConversation
    @ObservedObject var store: NativeCommunicatorStore

    @State private var draft = ""
    @State private var isLoadingMessages = false
    @State private var localMessages: [CommunicatorMessage] = []
    @State private var showCallPicker = false

    // Latest message id for this channel as seen by the 5s poll — used to
    // refresh this window when new messages arrive.
    private var liveLastMessageID: Int {
        store.conversations.first(where: { $0.channelID == conversation.channelID })?.lastMessage?.id ?? 0
    }

    var body: some View {
        VStack(spacing: 0) {
            titleBar
            messagesArea
            composer
        }
        .background(ForgeTheme.dark900)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear {
            Task {
                localMessages = (try? await store.loadMessages(for: conversation.channelID)) ?? []
                try? await store.markRead(for: conversation.channelID)
            }
        }
        .onChange(of: liveLastMessageID) { newID in
            // A new message arrived for this conversation — pull it into this
            // window and mark read since the window is open.
            guard newID > (localMessages.last?.id ?? 0) else { return }
            Task {
                localMessages = (try? await store.loadMessages(for: conversation.channelID)) ?? localMessages
                try? await store.markRead(for: conversation.channelID)
            }
        }
    }

    // MARK: - Title Bar

    private var titleBar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                ZStack(alignment: .topTrailing) {
                    conversationAvatar(size: 28)

                    if liveUnreadCount > 0 {
                        unreadBadge(count: liveUnreadCount)
                            .offset(x: 6, y: -6)
                    }
                }

                Text(conversation.name)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(ForgeTheme.silver)
                    .lineLimit(1)

                if let platform = conversation.bridgedPlatform {
                    platformPill(platform)
                }

                Spacer()

                videoCallButton
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
        Text(count > 99 ? "99+" : "\(count)")
            .font(.system(size: 9, weight: .bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 5)
            .frame(minWidth: 16, minHeight: 16)
            .background(ForgeTheme.coral)
            .clipShape(Capsule())
    }

    // MARK: - Video call

    private var videoCallButton: some View {
        Button {
            showCallPicker = true
        } label: {
            Image(systemName: "video")
                .font(.system(size: 14))
                .foregroundStyle(ForgeTheme.silver.opacity(0.6))
        }
        .buttonStyle(.plain)
        .help("Start video call")
        .popover(isPresented: $showCallPicker, arrowEdge: .bottom) {
            CallPickerView(
                conversation: conversation,
                onStartJitsi: { startJitsiCall() },
                onStartFaceTime: conversation.isDM ? { startFaceTimeCall() } : nil
            )
        }
    }

    private func jitsiRoomName() -> String {
        // Stable, collision-resistant room name tied to this specific channel.
        // Prefix with "Forge" so it's recognisable in the Jitsi UI.
        "Forge-\(conversation.workspaceID)-\(conversation.channelID)"
    }

    private func jitsiURL() -> URL {
        URL(string: "https://meet.jit.si/\(jitsiRoomName())")!
    }

    private func startJitsiCall() {
        showCallPicker = false
        let url = jitsiURL()
        let linkText = "📹 Join video call: \(url.absoluteString)"
        // Send the link as a message so the other person can join.
        Task {
            try? await store.sendMessage(to: conversation.channelID, body: linkText)
            localMessages = (try? await store.loadMessages(for: conversation.channelID)) ?? localMessages
        }
        NSWorkspace.shared.open(url)
    }

    private func startFaceTimeCall() {
        showCallPicker = false
        // Use conversation.name as the FaceTime address — works when it's an email.
        // For display-name DMs the user will see FaceTime's own contact lookup.
        let address = conversation.name
            .trimmingCharacters(in: .whitespaces)
            .addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? ""
        if let url = URL(string: "facetime://\(address)") {
            NSWorkspace.shared.open(url)
        }
    }

    // Live unread count from the store (updates as polling runs)
    private var liveUnreadCount: Int {
        store.conversations.first(where: { $0.channelID == conversation.channelID })?.unreadCount ?? 0
    }

    private var markReadButton: some View {
        Button {
            Task { try? await store.markRead(for: conversation.channelID) }
        } label: {
            Image(systemName: liveUnreadCount > 0 ? "checkmark.circle.fill" : "checkmark.circle")
                .font(.system(size: 14))
                .foregroundStyle(liveUnreadCount > 0 ? ForgeTheme.primary : ForgeTheme.silver.opacity(0.4))
        }
        .buttonStyle(.plain)
        .help("Mark as read")
    }

    // MARK: - Messages Area

    private var messagesArea: some View {
        ScrollViewReader { proxy in
            ScrollView {
                if localMessages.isEmpty {
                    emptyState
                } else {
                    LazyVStack(spacing: 2) {
                        ForEach(localMessages) { message in
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
            .onChange(of: localMessages.count) { _ in
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

                    composerEditor
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

            Text("Return to send  ·  ⇧ Return for a new line")
                .font(.system(size: 9))
                .foregroundStyle(ForgeTheme.silver.opacity(0.35))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 12)
                .padding(.bottom, 6)
        }
        .background(ForgeTheme.dark950)
    }

    @ViewBuilder
    private var composerEditor: some View {
        let editor = TextEditor(text: $draft)
            .font(.system(size: 13))
            .foregroundStyle(ForgeTheme.silver)
            .scrollContentBackground(.hidden)
            .background(.clear)
            .frame(minHeight: 20, maxHeight: 88)

        if #available(macOS 14.0, *) {
            editor.onKeyPress(keys: [.return], phases: .down) { press in
                // Shift+Return inserts a newline; plain Return sends.
                if press.modifiers.contains(.shift) { return .ignored }
                sendMessage()
                return .handled
            }
        } else {
            // macOS 13: no onKeyPress — ⌘Return still sends via the button shortcut.
            editor
        }
    }

    // MARK: - Actions

    private func sendMessage() {
        let body = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return }

        draft = ""
        Task {
            try? await store.sendMessage(to: conversation.channelID, body: body)
            localMessages = (try? await store.loadMessages(for: conversation.channelID)) ?? localMessages
        }
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
