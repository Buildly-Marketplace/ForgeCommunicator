import SwiftUI

struct ContactListView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var workspaces: [WorkspaceResponse] = []
    @State private var selectedWorkspace: WorkspaceResponse?
    @State private var members: [UserResponse] = []
    @State private var slackContacts: [SlackContact] = []
    @State private var isLoading = false
    @State private var searchText = ""

    private let api = APIClient.shared

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if workspaces.count > 1 {
                    Picker("Workspace", selection: $selectedWorkspace) {
                        ForEach(workspaces) { ws in
                            Text(ws.name).tag(ws as WorkspaceResponse?)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                }

                if isLoading {
                    ProgressView()
                        .tint(ForgeTheme.primary)
                        .frame(maxHeight: .infinity)
                } else {
                    List {
                        // Workspace members
                        if !filteredMembers.isEmpty {
                            Section {
                                ForEach(filteredMembers) { user in
                                    workspaceMemberRow(user)
                                }
                            } header: {
                                contactSectionHeader("Team", icon: "person.2.fill", count: filteredMembers.count, color: ForgeTheme.primary)
                            }
                        }

                        // Slack contacts
                        if !filteredSlackContacts.isEmpty {
                            Section {
                                ForEach(filteredSlackContacts) { contact in
                                    slackContactRow(contact)
                                }
                            } header: {
                                contactSectionHeader("Slack", icon: "number.square.fill", count: filteredSlackContacts.count, color: .purple)
                            }
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                }
            }
            .background(ForgeTheme.dark900)
            .forgeLogoToolbar(title: "Contacts")
            .searchable(text: $searchText, prompt: "Search people")
            .onChange(of: selectedWorkspace) { _, ws in
                if let ws { Task { await loadMembers(ws.id) } }
            }
        }
        .task {
            do {
                workspaces = try await api.workspaces()
                if let first = workspaces.first {
                    selectedWorkspace = first
                    await loadMembers(first.id)
                }
            } catch { /* silent */ }
            await loadSlackContacts()
        }
    }

    // MARK: - Section header

    private func contactSectionHeader(_ title: String, icon: String, count: Int, color: Color) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .foregroundStyle(color)
                .font(.caption)
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(ForgeTheme.textSecondary)
            Spacer()
            Text("\(count)")
                .font(.caption2.bold())
                .foregroundStyle(ForgeTheme.textMuted)
        }
    }

    // MARK: - Workspace member row

    private func workspaceMemberRow(_ user: UserResponse) -> some View {
        HStack(spacing: 12) {
            AvatarView(user: user, size: 40)
            VStack(alignment: .leading, spacing: 2) {
                Text(user.displayName)
                    .font(.body.weight(.medium))
                    .foregroundStyle(.white)
                if let title = user.title {
                    Text(title)
                        .font(.caption)
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
            }
            Spacer()

            Button {
                FaceTimeHelper.videoCall(email: user.email)
            } label: {
                Image(systemName: "video.fill")
                    .font(.caption)
                    .foregroundStyle(ForgeTheme.primary)
                    .padding(6)
                    .background(ForgeTheme.primary.opacity(0.15), in: Circle())
            }
            .buttonStyle(.plain)

            Button {
                FaceTimeHelper.audioCall(email: user.email)
            } label: {
                Image(systemName: "phone.fill")
                    .font(.caption)
                    .foregroundStyle(.green)
                    .padding(6)
                    .background(Color.green.opacity(0.15), in: Circle())
            }
            .buttonStyle(.plain)

            Circle()
                .fill(user.isOnline ? .green : ForgeTheme.dark500)
                .frame(width: 8, height: 8)
        }
        .padding(.vertical, 2)
        .listRowBackground(ForgeTheme.dark900)
    }

    // MARK: - Slack contact row

    private func slackContactRow(_ contact: SlackContact) -> some View {
        HStack(spacing: 12) {
            slackAvatar(contact, size: 40)
            VStack(alignment: .leading, spacing: 2) {
                Text(contact.realName.isEmpty ? contact.displayName : contact.realName)
                    .font(.body.weight(.medium))
                    .foregroundStyle(.white)
                if let title = contact.title, !title.isEmpty {
                    Text(title)
                        .font(.caption)
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
            }
            Spacer()

            Image(systemName: "number.square.fill")
                .font(.caption)
                .foregroundStyle(.purple.opacity(0.6))

            Circle()
                .fill(contact.isOnline ? .green : ForgeTheme.dark500)
                .frame(width: 8, height: 8)
        }
        .padding(.vertical, 2)
        .listRowBackground(ForgeTheme.dark900)
    }

    @ViewBuilder
    private func slackAvatar(_ contact: SlackContact, size: CGFloat) -> some View {
        if let urlStr = contact.avatarUrl, let url = URL(string: urlStr) {
            AsyncImage(url: url) { image in
                image.resizable().scaledToFill()
            } placeholder: {
                slackInitials(contact, size: size)
            }
            .frame(width: size, height: size)
            .clipShape(Circle())
        } else {
            slackInitials(contact, size: size)
        }
    }

    private func slackInitials(_ contact: SlackContact, size: CGFloat) -> some View {
        let name = contact.realName.isEmpty ? contact.displayName : contact.realName
        let parts = name.split(separator: " ")
        let initials: String = parts.count >= 2
            ? String(parts[0].prefix(1) + parts[1].prefix(1)).uppercased()
            : String(name.prefix(2)).uppercased()
        return Circle()
            .fill(
                LinearGradient(
                    colors: [Color.purple.opacity(0.3), Color.purple.opacity(0.15)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .frame(width: size, height: size)
            .overlay {
                Text(initials)
                    .font(.system(size: size * 0.38, weight: .semibold))
                    .foregroundStyle(.purple)
            }
    }

    // MARK: - Filtering

    private var filteredMembers: [UserResponse] {
        if searchText.isEmpty { return members }
        let q = searchText.lowercased()
        return members.filter {
            $0.displayName.lowercased().contains(q) ||
            $0.email.lowercased().contains(q) ||
            ($0.title?.lowercased().contains(q) ?? false)
        }
    }

    private var filteredSlackContacts: [SlackContact] {
        if searchText.isEmpty { return slackContacts }
        let q = searchText.lowercased()
        return slackContacts.filter {
            $0.displayName.lowercased().contains(q) ||
            $0.realName.lowercased().contains(q) ||
            ($0.email?.lowercased().contains(q) ?? false) ||
            ($0.title?.lowercased().contains(q) ?? false)
        }
    }

    // MARK: - Data loading

    private func loadMembers(_ workspaceId: Int) async {
        isLoading = true
        defer { isLoading = false }
        do {
            members = try await api.workspaceMembers(workspaceId: workspaceId)
        } catch { /* silent */ }
    }

    private func loadSlackContacts() async {
        do {
            slackContacts = try await api.slackContacts()
        } catch { /* silent */ }
    }
}
