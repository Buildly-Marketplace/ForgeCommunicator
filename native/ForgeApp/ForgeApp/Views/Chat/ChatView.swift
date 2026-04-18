import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

struct ChatView: View {
    let channelId: Int
    let workspaceId: Int
    let title: String
    let bridgedPlatform: String?

    @StateObject private var vm: ChatViewModel
    @EnvironmentObject var authVM: AuthViewModel
    @State private var draft = ""
    @FocusState private var inputFocused: Bool

    private let webBaseURL = "https://comms.buildly.io"

    init(channelId: Int, workspaceId: Int, title: String, bridgedPlatform: String? = nil) {
        self.channelId = channelId
        self.workspaceId = workspaceId
        self.title = title
        self.bridgedPlatform = bridgedPlatform
        _vm = StateObject(wrappedValue: ChatViewModel(channelId: channelId, workspaceId: workspaceId))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 2) {
                        // Pull-to-load-older sentinel
                        Color.clear
                            .frame(height: 1)
                            .onAppear { Task { await vm.loadOlder() } }

                        ForEach(vm.messages) { msg in
                            MessageBubble(
                                message: msg,
                                isMe: msg.userId == authVM.currentUser?.id
                            )
                            .id(msg.id)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }
                .onChange(of: vm.messages.count) { _, _ in
                    if let last = vm.messages.last {
                        withAnimation(.easeOut(duration: 0.2)) {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }

            Divider()
                .overlay(ForgeTheme.dark600)

            // Input bar
            HStack(spacing: 8) {
                TextField("Message…", text: $draft, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...5)
                    .focused($inputFocused)
                    .onSubmit { sendIfReady() }
                    .padding(10)
                    .background(ForgeTheme.dark700, in: RoundedRectangle(cornerRadius: 20))
                    .foregroundStyle(.white)

                Button {
                    sendIfReady()
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                        .foregroundStyle(draft.trimmingCharacters(in: .whitespaces).isEmpty ? ForgeTheme.dark500 : ForgeTheme.primary)
                }
                .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty || vm.isSending)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            #if os(iOS)
            .padding(.bottom, 2)
            #endif
            .background(ForgeTheme.dark800)
        }
        .background(ForgeTheme.dark900)
        .navigationTitle(title)
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(.visible, for: .navigationBar)
        #endif
        .toolbar {
            ToolbarItemGroup(placement: .automatic) {
                if let otherEmail = vm.otherUserEmail {
                    Button {
                        FaceTimeHelper.videoCall(email: otherEmail)
                    } label: {
                        Image(systemName: "video.fill")
                            .foregroundStyle(ForgeTheme.primary)
                    }
                    .help("FaceTime video call")

                    Button {
                        FaceTimeHelper.audioCall(email: otherEmail)
                    } label: {
                        Image(systemName: "phone.fill")
                            .foregroundStyle(.green)
                    }
                    .help("FaceTime audio call")
                }

                Button {
                    openInWeb()
                } label: {
                    Image(systemName: "safari")
                        .foregroundStyle(ForgeTheme.primary)
                }
                .help("Open in web browser")
            }
        }
        .task {
            // Auto-import messages for bridged channels
            if bridgedPlatform != nil {
                try? await APIClient.shared.importMessages(channelId: channelId)
            }
            await vm.loadInitial()
        }
        // Simple polling for new messages (will be replaced by WebSocket)
        .task {
            var previousCount = vm.messages.count
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                await vm.catchUp()
                if vm.messages.count > previousCount {
                    NotificationService.shared.playSound()
                    previousCount = vm.messages.count
                }
            }
        }
    }

    private func sendIfReady() {
        let text = draft
        draft = ""
        Task { await vm.send(text) }
    }

    private func openInWeb() {
        let urlString = "\(webBaseURL)/workspaces/\(workspaceId)/channels/\(channelId)"
        guard let url = URL(string: urlString) else { return }
        #if canImport(UIKit)
        UIApplication.shared.open(url)
        #elseif canImport(AppKit)
        NSWorkspace.shared.open(url)
        #endif
    }
}

// MARK: - Message bubble

struct MessageBubble: View {
    let message: MessageResponse
    let isMe: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if isMe { Spacer(minLength: 60) }

            if !isMe {
                AvatarView(user: message.author, size: 32)
            }

            VStack(alignment: isMe ? .trailing : .leading, spacing: 2) {
                if !isMe {
                    Text(message.authorName)
                        .font(.caption.bold())
                        .foregroundStyle(ForgeTheme.textSecondary)
                }

                Text(message.body)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(isMe ? ForgeTheme.primary : ForgeTheme.dark700, in: bubbleShape)
                    .foregroundStyle(.white)

                HStack(spacing: 4) {
                    Text(message.createdAt, style: .time)
                        .font(.caption2)
                        .foregroundStyle(ForgeTheme.textMuted)
                    if message.isEdited {
                        Text("edited")
                            .font(.caption2)
                            .foregroundStyle(ForgeTheme.textMuted)
                    }
                    if message.threadReplyCount > 0 {
                        Text("💬 \(message.threadReplyCount)")
                            .font(.caption2)
                            .foregroundStyle(ForgeTheme.primary)
                    }
                }
            }

            if !isMe { Spacer(minLength: 60) }
        }
        .padding(.vertical, 2)
    }

    private var bubbleShape: some Shape {
        RoundedRectangle(cornerRadius: 16)
    }
}
