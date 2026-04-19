import SwiftUI

/// User status picker — set status icon + message, or sync from Google Calendar.
struct StatusPickerView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var selectedStatus: UserStatusOption = .active
    @State private var statusMessage: String = ""
    @State private var googleConnected = false
    @State private var useGoogleCalendar = false
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            List {
                // Standard status options
                Section("Status") {
                    ForEach(UserStatusOption.allCases.filter { !$0.isCalendarStatus }) { option in
                        statusRow(option)
                    }
                }

                // Calendar-based statuses
                Section("Calendar") {
                    ForEach(UserStatusOption.allCases.filter { $0.isCalendarStatus }) { option in
                        statusRow(option)
                    }
                    Text("These statuses sync automatically when Google Calendar is connected.")
                        .font(.caption)
                        .foregroundStyle(ForgeTheme.textSecondary)
                        .listRowBackground(ForgeTheme.dark800)
                }

                // Custom message
                Section("Status Message") {
                    TextField("What's your status?", text: $statusMessage)
                        .forgeDarkInput()
                        .listRowBackground(ForgeTheme.dark800)
                }

                // Google Calendar integration
                Section {
                    if googleConnected {
                        Toggle(isOn: $useGoogleCalendar) {
                            HStack(spacing: 10) {
                                Image(systemName: "calendar")
                                    .foregroundStyle(.red)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Google Calendar Status")
                                        .font(.body.weight(.medium))
                                        .foregroundStyle(.white)
                                    Text("Auto-update status from calendar events")
                                        .font(.caption)
                                        .foregroundStyle(ForgeTheme.textSecondary)
                                }
                            }
                        }
                        .tint(ForgeTheme.primary)
                        .listRowBackground(ForgeTheme.dark800)

                        Button(role: .destructive) {
                            googleConnected = false
                            useGoogleCalendar = false
                        } label: {
                            Label("Disconnect Google", systemImage: "xmark.circle")
                        }
                        .listRowBackground(ForgeTheme.dark800)
                    } else {
                        Button {
                            connectGoogle()
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: "g.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(.red)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Connect Google Account")
                                        .font(.body.weight(.medium))
                                        .foregroundStyle(.white)
                                    Text("Sign in with Google OAuth to sync calendar status")
                                        .font(.caption)
                                        .foregroundStyle(ForgeTheme.textSecondary)
                                }
                            }
                        }
                        .listRowBackground(ForgeTheme.dark800)
                    }
                } header: {
                    Text("Google Calendar")
                }
            }
            .scrollContentBackground(.hidden)
            .background(ForgeTheme.dark900)
            .navigationTitle("Set Status")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveStatus()
                    }
                    .disabled(isSaving)
                    .foregroundStyle(ForgeTheme.primary)
                }
            }
        }
        .onAppear {
            if let user = authVM.currentUser {
                selectedStatus = UserStatusOption(rawValue: user.status) ?? .active
                statusMessage = user.statusMessage ?? ""
            }
        }
    }

    private func connectGoogle() {
        // Open Google OAuth flow via the web backend
        let baseURL = "https://comms.buildly.io"
        if let url = URL(string: "\(baseURL)/integrations/google/connect") {
            #if canImport(AppKit)
            NSWorkspace.shared.open(url)
            #endif
            // After returning from OAuth, the backend stores the token
            // For now, mark as connected (real impl would poll/callback)
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                googleConnected = true
                useGoogleCalendar = true
            }
        }
    }

    private func saveStatus() {
        isSaving = true
        Task {
            do {
                let update = ProfileUpdate(
                    status: selectedStatus.rawValue,
                    statusMessage: statusMessage.isEmpty ? nil : statusMessage
                )
                let updatedUser = try await APIClient.shared.updateProfile(update)
                authVM.currentUser = updatedUser
                dismiss()
            } catch {
                isSaving = false
            }
        }
    }

    private func statusRow(_ option: UserStatusOption) -> some View {
        Button {
            selectedStatus = option
        } label: {
            HStack(spacing: 12) {
                Text(option.emoji)
                    .font(.title3)
                VStack(alignment: .leading, spacing: 2) {
                    Text(option.label)
                        .font(.body.weight(.medium))
                        .foregroundStyle(.white)
                    Text(option.description)
                        .font(.caption)
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
                Spacer()
                if selectedStatus == option {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(ForgeTheme.primary)
                }
            }
        }
        .listRowBackground(ForgeTheme.dark800)
    }
}

// MARK: - Status Options

enum UserStatusOption: String, CaseIterable, Identifiable {
    case active
    case away
    case inMeeting = "in_meeting"
    case onACall = "on_a_call"
    case dnd
    case offline

    var id: String { rawValue }

    var emoji: String {
        switch self {
        case .active: return "🟢"
        case .away: return "🟡"
        case .inMeeting: return "📅"
        case .onACall: return "📞"
        case .dnd: return "🔴"
        case .offline: return "⚫"
        }
    }

    var label: String {
        switch self {
        case .active: return "Available"
        case .away: return "Away"
        case .inMeeting: return "In a Meeting"
        case .onACall: return "On a Call"
        case .dnd: return "Do Not Disturb"
        case .offline: return "Offline"
        }
    }

    var description: String {
        switch self {
        case .active: return "You're available and online"
        case .away: return "You're away from your desk"
        case .inMeeting: return "Busy — synced from your calendar"
        case .onACall: return "Currently on a call"
        case .dnd: return "Pause all notifications"
        case .offline: return "Appear offline to others"
        }
    }

    /// Whether this status can be auto-set from Google Calendar events.
    var isCalendarStatus: Bool {
        switch self {
        case .inMeeting, .onACall: return true
        default: return false
        }
    }
}
