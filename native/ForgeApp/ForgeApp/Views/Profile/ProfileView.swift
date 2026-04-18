import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

struct ProfileView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var showStatusPicker = false

    var body: some View {
        NavigationStack {
            List {
                if let user = authVM.currentUser {
                    Section {
                        HStack(spacing: 16) {
                            AvatarView(user: user, size: 64)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(user.displayName)
                                    .font(.title3.bold())
                                    .foregroundStyle(.white)
                                Text(user.email)
                                    .font(.subheadline)
                                    .foregroundStyle(ForgeTheme.textSecondary)
                                if let title = user.title {
                                    Text(title)
                                        .font(.caption)
                                        .foregroundStyle(ForgeTheme.textMuted)
                                }
                            }
                        }
                        .padding(.vertical, 8)
                        .listRowBackground(ForgeTheme.dark800)
                    }

                    if let bio = user.bio, !bio.isEmpty {
                        Section("Bio") {
                            Text(bio)
                                .foregroundStyle(.white)
                        }
                        .listRowBackground(ForgeTheme.dark800)
                    }

                    // Status section with tap-to-change
                    Section("Status") {
                        Button {
                            showStatusPicker = true
                        } label: {
                            HStack {
                                Circle()
                                    .fill(statusColor(user.status))
                                    .frame(width: 10, height: 10)
                                Text(user.status.capitalized)
                                    .foregroundStyle(.white)
                                if let msg = user.statusMessage {
                                    Text("— \(msg)")
                                        .foregroundStyle(ForgeTheme.textSecondary)
                                }
                                Spacer()
                                Image(systemName: "pencil.circle")
                                    .foregroundStyle(ForgeTheme.primary)
                            }
                        }
                        .listRowBackground(ForgeTheme.dark800)
                    }

                    // Google Calendar sync indicator
                    Section("Connected Accounts") {
                        NavigationLink {
                            IntegrationsView()
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: "link.circle.fill")
                                    .font(.title3)
                                    .foregroundStyle(ForgeTheme.primary)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Integrations")
                                        .font(.body)
                                        .foregroundStyle(.white)
                                    Text("Slack, Discord & more")
                                        .font(.caption)
                                        .foregroundStyle(ForgeTheme.textSecondary)
                                }
                                Spacer()
                            }
                        }
                        .listRowBackground(ForgeTheme.dark800)

                        Button {
                            openGoogleConnect()
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: "g.circle.fill")
                                    .font(.title3)
                                    .foregroundStyle(.red)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Google Account")
                                        .font(.body)
                                        .foregroundStyle(.white)
                                    Text("Connect for calendar status sync")
                                        .font(.caption)
                                        .foregroundStyle(ForgeTheme.textSecondary)
                                }
                                Spacer()
                                Image(systemName: "arrow.up.right.square")
                                    .foregroundStyle(ForgeTheme.textMuted)
                            }
                        }
                        .listRowBackground(ForgeTheme.dark800)
                    }
                }

                Section {
                    Button("Sign Out", role: .destructive) {
                        Task { await authVM.logout() }
                    }
                    .listRowBackground(ForgeTheme.dark800)
                }
            }
            .scrollContentBackground(.hidden)
            .background(ForgeTheme.dark900)
            .forgeLogoToolbar(title: "Profile")
            .sheet(isPresented: $showStatusPicker) {
                StatusPickerView()
                    .environmentObject(authVM)
            }
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "active": return .green
        case "away": return .yellow
        case "dnd": return .red
        default: return ForgeTheme.dark500
        }
    }

    private func openGoogleConnect() {
        if let url = URL(string: "https://comms.buildly.io/integrations/google/connect") {
            #if canImport(AppKit)
            NSWorkspace.shared.open(url)
            #endif
        }
    }
}
