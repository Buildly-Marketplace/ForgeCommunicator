import SwiftUI

// MARK: - SlackConversationsView

/// Dedicated view for all bridged Slack conversations (DMs and channels).
/// Shown in its own tab so Slack messages don't clutter the main Messages inbox.
struct SlackConversationsView: View {
    @StateObject private var vm = ConversationListViewModel()
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var notificationService: NotificationService
    @State private var filter: SlackFilter = .dms
    @State private var slackConnected = false
    @State private var workspaces: [WorkspaceResponse] = []
    @State private var selectedWorkspaceId: Int?

    private let api = APIClient.shared
    private let webBaseURL = "https://comms.buildly.io"

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Workspace + filter picker
                HStack(spacing: 8) {
                    if workspaces.count > 1 {
                        Menu {
                            Button { selectedWorkspaceId = nil } label: {
                                if selectedWorkspaceId == nil {
                                    Label("All Workspaces", systemImage: "checkmark")
                                } else {
                                    Text("All Workspaces")
                                }
                            }
                            ForEach(workspaces) { ws in
                                Button { selectedWorkspaceId = ws.id } label: {
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
                        ForEach(SlackFilter.allCases) { f in
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
                            .tint(.purple)
                            .frame(maxHeight: .infinity)
                    } else if !slackConnected {
                        notConnectedView
                    } else if filteredConversations.isEmpty {
                        ContentUnavailableView(
                            filter.emptyTitle,
                            systemImage: filter.emptyIcon,
                            description: Text(filter.emptyDescription)
                        )
                    } else {
                        slackList
                    }
                }
            }
            .background(ForgeTheme.dark900)
            .navigationTitle("Slack")
            .navigationDestination(for: ConversationPreview.self) { conv in
                ChatView(
                    channelId: conv.channelId,
                    workspaceId: conv.workspaceId,
                    title: strippedName(conv.name),
                    bridgedPlatform: conv.bridgedPlatform
                )
            }
        }
        .task {
            await vm.load()
            await loadWorkspaces()
            await loadIntegrationStatus()
        }
    }

    // MARK: - Not connected state

    private var notConnectedView: some View {
        VStack(spacing: 16) {
            Image(systemName: "number.square.fill")
                .font(.system(size: 52))
                .foregroundStyle(.purple.opacity(0.7))
            Text("Slack Not Connected")
                .font(.title3.bold())
                .foregroundStyle(.white)
            Text("Connect your Slack workspace in Profile → Integrations to see your Slack messages here.")
                .font(.subheadline)
                .foregroundStyle(ForgeTheme.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - List

    private var slackList: some View {
        List {
            Section {
                ForEach(filteredConversations) { conv in
                    NavigationLink(value: conv) {
                        ConversationRow(
                            conversation: conv,
                            currentUserId: authVM.currentUser?.id,
                            webBaseURL: webBaseURL
                        )
                    }
                    .listRowBackground(ForgeTheme.dark900)
                    .simultaneousGesture(TapGesture().onEnded {
                        vm.markChannelRead(channelId: conv.channelId)
                    })
                    .swipeActions(edge: .trailing) {
                        Button { openInWeb(conv) } label: {
                            Label("Open Web", systemImage: "safari")
                        }
                        .tint(.purple)
                    }
                }
            } header: {
                HStack(spacing: 6) {
                    Image(systemName: filter == .dms ? "bubble.left.fill" : "number.square.fill")
                        .foregroundStyle(.purple)
                        .font(.caption)
                    Text(filter == .dms ? "Slack DMs" : "Slack Channels")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(ForgeTheme.textSecondary)
                    Spacer()
                    if unreadCount > 0 {
                        Text("\(unreadCount)")
                            .font(.caption2.bold())
                            .foregroundStyle(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(.purple, in: Capsule())
                    }
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

    // MARK: - Filtering

    private var workspaceFiltered: [ConversationPreview] {
        let slack = vm.conversations.filter { $0.bridgedPlatform == "slack" }
        if let wsId = selectedWorkspaceId {
            return slack.filter { $0.workspaceId == wsId }
        }
        return slack
    }

    /// Known Slack bot/app names to filter out of DMs
    private static let slackBotNames: Set<String> = [
        "slackbot", "calendly", "canva", "coda", "figma", "github", "github (legacy)",
        "google calendar", "google cloud monitoring", "google drive", "notion",
        "zoom", "jira", "jira cloud", "asana", "trello", "linear", "butler",
        "deal won notification", "item status notification", "polly", "donut",
        "standuply", "geekbot", "deactivated user", "zapier", "ifttt",
        "hubspot", "salesforce", "mailchimp", "intercom", "pagerduty",
        "datadog", "sentry", "pull reminders", "simple poll", "range",
        "slogging by hackernoon", "spacetime", "statuspage", "sup",
        "cloze", "sameroom", "standup", "sunsama", "aloha",
    ]

    private var slackDMs: [ConversationPreview] {
        workspaceFiltered.filter { conv in
            guard conv.isDm else { return false }
            let stripped = conv.name
                .replacingOccurrences(of: "SLACK:", with: "")
                .lowercased()
            if stripped.hasPrefix("mpdm-") { return false }
            if Self.slackBotNames.contains(stripped) { return false }
            return true
        }
    }

    private var slackChannels: [ConversationPreview] {
        workspaceFiltered.filter { !$0.isDm }
    }

    private var filteredConversations: [ConversationPreview] {
        filter == .dms ? slackDMs : slackChannels
    }

    private var unreadCount: Int {
        filteredConversations.reduce(0) { $0 + $1.unreadCount }
    }

    // MARK: - Helpers

    private var selectedWorkspaceName: String {
        if let wsId = selectedWorkspaceId,
           let ws = workspaces.first(where: { $0.id == wsId }) {
            return ws.name
        }
        return "All"
    }

    private func strippedName(_ name: String) -> String {
        var n = name
        for prefix in ["SLACK:", "DISCORD:"] {
            if n.hasPrefix(prefix) { n = String(n.dropFirst(prefix.count)) }
        }
        return n
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

    private func loadWorkspaces() async {
        do { workspaces = try await api.workspaces() } catch { /* silent */ }
    }

    private func loadIntegrationStatus() async {
        do {
            let status = try await api.integrationStatus()
            slackConnected = status.slackConnected
        } catch { /* silent */ }
    }
}

// MARK: - Filter enum

enum SlackFilter: String, CaseIterable, Identifiable {
    case dms
    case channels

    var id: String { rawValue }

    var label: String {
        switch self {
        case .dms: return "DMs"
        case .channels: return "Channels"
        }
    }

    var emptyTitle: String {
        switch self {
        case .dms: return "No Slack DMs"
        case .channels: return "No Slack Channels"
        }
    }

    var emptyIcon: String {
        switch self {
        case .dms: return "bubble.left"
        case .channels: return "number.square"
        }
    }

    var emptyDescription: String {
        switch self {
        case .dms: return "Your Slack direct messages will appear here."
        case .channels: return "Your synced Slack channels will appear here."
        }
    }
}
