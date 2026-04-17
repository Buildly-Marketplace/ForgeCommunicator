import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var authVM: AuthViewModel

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
                                Text(user.email)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                                if let title = user.title {
                                    Text(title)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        .padding(.vertical, 8)
                    }

                    if let bio = user.bio, !bio.isEmpty {
                        Section("Bio") {
                            Text(bio)
                        }
                    }

                    Section("Status") {
                        HStack {
                            Circle()
                                .fill(statusColor(user.status))
                                .frame(width: 10, height: 10)
                            Text(user.status.capitalized)
                            if let msg = user.statusMessage {
                                Text("— \(msg)")
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                Section {
                    Button("Sign Out", role: .destructive) {
                        Task { await authVM.logout() }
                    }
                }
            }
            .navigationTitle("Profile")
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "active": return .green
        case "away": return .yellow
        case "dnd": return .red
        default: return .gray
        }
    }
}
