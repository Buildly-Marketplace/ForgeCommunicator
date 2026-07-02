import SwiftUI

// MARK: - ConversationRailView

struct ConversationRailView: View {
    @ObservedObject var store: NativeCommunicatorStore
    @ObservedObject var accountStore: AccountStore
    @Binding var selectedSourceID: UUID?
    var onOpenConversation: (CommunicatorConversation) -> Void
    var onOpenSettings: () -> Void

    @State private var searchText: String = ""

    // MARK: Filtered conversations

    private var filteredConversations: [CommunicatorConversation] {
        guard !searchText.isEmpty else { return store.conversations }
        let q = searchText.lowercased()
        return store.conversations.filter {
            $0.name.lowercased().contains(q) ||
            ($0.lastMessage?.body.lowercased().contains(q) == true)
        }
    }

    private var unreadConversations: [CommunicatorConversation] {
        filteredConversations.filter { $0.unreadCount > 0 }
    }

    private var readConversations: [CommunicatorConversation] {
        filteredConversations.filter { $0.unreadCount == 0 }
    }

    // MARK: Body

    var body: some View {
        VStack(spacing: 0) {
            headerBar
            sourceSwitcher
            searchBar
            conversationList
            userFooter
        }
        .frame(minWidth: 220, idealWidth: 260, maxWidth: 300)
        .background(ForgeTheme.dark900)
    }

    // MARK: - Header

    private var headerBar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                ForgeLogoIcon(size: 22)

                Text("Forge")
                    .font(ForgeTheme.headingFont(size: 13, weight: .semibold))
                    .foregroundColor(ForgeTheme.white)

                Spacer()

                Circle()
                    .fill(ForgeTheme.statusOnline)
                    .frame(width: 8, height: 8)

                Button(action: onOpenSettings) {
                    Image(systemName: "gearshape")
                        .font(.system(size: 13, weight: .regular))
                        .foregroundColor(ForgeTheme.silver.opacity(0.7))
                }
                .buttonStyle(.plain)
                .help("Settings")
            }
            .padding(.horizontal, 12)
            .frame(height: 52)

            Divider()
                .background(ForgeTheme.glassBorder)
        }
        .background(ForgeTheme.dark950)
    }

    // MARK: - Source Switcher

    private var sourceSwitcher: some View {
        VStack(spacing: 0) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(accountStore.accounts) { source in
                        SourcePillButton(
                            source: source,
                            isSelected: selectedSourceID == source.id,
                            onTap: { selectedSourceID = source.id }
                        )
                    }

                    Button(action: onOpenSettings) {
                        Image(systemName: "plus")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(ForgeTheme.silver.opacity(0.6))
                            .frame(width: 28, height: 28)
                            .background(ForgeTheme.dark700.opacity(0.5))
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)
                    .help("Add source")
                }
                .padding(.horizontal, 10)
            }
            .frame(height: 48)

            Divider()
                .background(ForgeTheme.glassBorder)
        }
        .background(ForgeTheme.dark900)
    }

    // MARK: - Search Bar

    private var searchBar: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 11, weight: .regular))
                .foregroundColor(ForgeTheme.silver.opacity(0.45))

            TextField("Search...", text: $searchText)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
                .foregroundColor(ForgeTheme.white)
        }
        .padding(.horizontal, 8)
        .frame(height: 28)
        .background(ForgeTheme.dark800.opacity(0.8))
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .strokeBorder(ForgeTheme.glassBorder, lineWidth: 1)
        )
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .frame(height: 36)
    }

    // MARK: - Conversation List

    private var conversationList: some View {
        ScrollView(.vertical, showsIndicators: false) {
            LazyVStack(spacing: 0, pinnedViews: [.sectionHeaders]) {
                if !unreadConversations.isEmpty {
                    Section {
                        ForEach(unreadConversations) { conversation in
                            RailConversationRow(
                                conversation: conversation,
                                isSelected: store.selectedConversationID == conversation.channelID,
                                onTap: { onOpenConversation(conversation) }
                            )
                        }
                    } header: {
                        railSectionHeader("Unread")
                    }
                }

                if !readConversations.isEmpty {
                    Section {
                        ForEach(readConversations) { conversation in
                            RailConversationRow(
                                conversation: conversation,
                                isSelected: store.selectedConversationID == conversation.channelID,
                                onTap: { onOpenConversation(conversation) }
                            )
                        }
                    } header: {
                        if !unreadConversations.isEmpty {
                            railSectionHeader("All")
                        }
                    }
                }

                if filteredConversations.isEmpty {
                    Text(searchText.isEmpty ? "No conversations" : "No results")
                        .font(.system(size: 11))
                        .foregroundColor(ForgeTheme.silver.opacity(0.4))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 24)
                }
            }
        }
        .frame(maxHeight: .infinity)
        .background(ForgeTheme.dark900)
    }

    private func railSectionHeader(_ title: String) -> some View {
        HStack {
            Text(title.uppercased())
                .font(.system(size: 9, weight: .semibold))
                .foregroundColor(ForgeTheme.silver.opacity(0.45))
                .tracking(0.8)
            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .background(ForgeTheme.dark900)
    }

    // MARK: - User Footer

    private var userFooter: some View {
        VStack(spacing: 0) {
            Divider()
                .background(ForgeTheme.glassBorder)

            HStack(spacing: 8) {
                InitialsAvatar(
                    name: store.currentUserDisplayName ?? "Me",
                    size: 32
                )

                VStack(alignment: .leading, spacing: 1) {
                    Text(store.currentUserDisplayName ?? "Me")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(ForgeTheme.white)
                        .lineLimit(1)

                    HStack(spacing: 4) {
                        Circle()
                            .fill(ForgeTheme.statusOnline)
                            .frame(width: 6, height: 6)
                        Text("Online")
                            .font(.system(size: 10))
                            .foregroundColor(ForgeTheme.silver.opacity(0.55))
                    }
                }

                Spacer()

                Button(action: onOpenSettings) {
                    Image(systemName: "gearshape")
                        .font(.system(size: 12, weight: .regular))
                        .foregroundColor(ForgeTheme.silver.opacity(0.6))
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 12)
            .frame(height: 52)
        }
        .background(ForgeTheme.dark950)
    }
}

// MARK: - SourcePillButton

private struct SourcePillButton: View {
    let source: Source
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 4) {
                Image(systemName: iconName(for: source.type))
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(isSelected ? ForgeTheme.dark950 : ForgeTheme.silver.opacity(0.7))
            }
            .padding(.horizontal, 10)
            .frame(height: 28)
            .background(
                isSelected
                    ? ForgeTheme.primary
                    : ForgeTheme.dark700.opacity(0.5)
            )
            .clipShape(Capsule())
            .overlay(
                Capsule()
                    .strokeBorder(
                        isSelected ? ForgeTheme.primary.opacity(0.4) : ForgeTheme.glassBorder,
                        lineWidth: 1
                    )
            )
        }
        .buttonStyle(.plain)
        .help(source.displayName)
    }

    private func iconName(for type: SourceType) -> String {
        switch type {
        case .communicator: return "bubble.left.and.bubble.right.fill"
        case .whatsapp:     return "phone.bubble.left.fill"
        case .signal:       return "lock.shield.fill"
        case .telegram:     return "paperplane.fill"
        }
    }
}

// MARK: - RailConversationRow

private struct RailConversationRow: View {
    let conversation: CommunicatorConversation
    let isSelected: Bool
    let onTap: () -> Void

    @State private var isHovered = false

    private var rowBackground: Color {
        if isSelected { return ForgeTheme.primary.opacity(0.12) }
        if isHovered  { return ForgeTheme.dark700.opacity(0.4) }
        return .clear
    }

    var body: some View {
        HStack(spacing: 8) {
            InitialsAvatar(name: conversation.name, size: 34)

            VStack(alignment: .leading, spacing: 2) {
                Text(conversation.name)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(ForgeTheme.white)
                    .lineLimit(1)

                if let preview = conversation.lastMessage?.body, !preview.isEmpty {
                    Text(preview)
                        .font(.system(size: 11))
                        .foregroundColor(ForgeTheme.silver.opacity(0.55))
                        .lineLimit(1)
                } else {
                    Text("No messages yet")
                        .font(.system(size: 11))
                        .foregroundColor(ForgeTheme.silver.opacity(0.3))
                        .lineLimit(1)
                }
            }

            Spacer(minLength: 4)

            VStack(alignment: .trailing, spacing: 4) {
                if let lastMsg = conversation.lastMessage {
                    Text(relativeTimestamp(lastMsg.createdAt))
                        .font(.system(size: 10))
                        .foregroundColor(ForgeTheme.silver.opacity(0.4))
                }

                if conversation.unreadCount > 0 {
                    Text("\(conversation.unreadCount)")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 5)
                        .frame(minWidth: 18, minHeight: 16)
                        .background(ForgeTheme.primary)
                        .clipShape(Capsule())
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(rowBackground)
        .contentShape(Rectangle())
        .onTapGesture(perform: onTap)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.12)) {
                isHovered = hovering
            }
        }
    }

    private func relativeTimestamp(_ date: Date) -> String {
        let now = Date()
        let diff = now.timeIntervalSince(date)

        if diff < 60 { return "now" }
        if diff < 3600 {
            let mins = Int(diff / 60)
            return "\(mins)m"
        }
        if diff < 86400 {
            let hours = Int(diff / 3600)
            return "\(hours)h"
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return formatter.string(from: date)
    }
}

// MARK: - InitialsAvatar

private struct InitialsAvatar: View {
    let name: String
    let size: CGFloat

    private var initials: String {
        let parts = name.split(separator: " ").prefix(2)
        return parts.compactMap { $0.first.map { String($0).uppercased() } }.joined()
    }

    private var gradientColors: [Color] {
        let palette: [(Color, Color)] = [
            (ForgeTheme.primary, Color(hex: "#1C56B8")),
            (ForgeTheme.violet, Color(hex: "#4A34CC")),
            (ForgeTheme.green, Color(hex: "#1A8C5E")),
            (ForgeTheme.amber, Color(hex: "#CC8800")),
            (ForgeTheme.coral, Color(hex: "#CC3B3B")),
        ]
        let index = abs(name.hashValue) % palette.count
        return [palette[index].0, palette[index].1]
    }

    var body: some View {
        ZStack {
            LinearGradient(
                colors: gradientColors,
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            Text(initials.isEmpty ? "?" : initials)
                .font(.system(size: size * 0.38, weight: .semibold))
                .foregroundColor(.white)
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }
}
