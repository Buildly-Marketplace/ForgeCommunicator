import SwiftUI

struct ContactListView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var workspaces: [WorkspaceResponse] = []
    @State private var selectedWorkspace: WorkspaceResponse?
    @State private var members: [UserResponse] = []
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
                    List(filteredMembers) { user in
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
                            Circle()
                                .fill(user.isOnline ? .green : ForgeTheme.dark500)
                                .frame(width: 8, height: 8)
                        }
                        .padding(.vertical, 2)
                        .listRowBackground(ForgeTheme.dark900)
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
        }
    }

    private var filteredMembers: [UserResponse] {
        if searchText.isEmpty { return members }
        let q = searchText.lowercased()
        return members.filter {
            $0.displayName.lowercased().contains(q) ||
            $0.email.lowercased().contains(q) ||
            ($0.title?.lowercased().contains(q) ?? false)
        }
    }

    private func loadMembers(_ workspaceId: Int) async {
        isLoading = true
        defer { isLoading = false }
        do {
            members = try await api.workspaceMembers(workspaceId: workspaceId)
        } catch { /* silent */ }
    }
}
