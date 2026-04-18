import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

/// View for managing Slack and Discord integrations.
struct IntegrationsView: View {
    @State private var slackConnected = false
    @State private var discordConnected = false
    @State private var slackWorkspace: String = ""
    @State private var discordServer: String = ""
    @State private var isLoading = true
    @State private var error: String?

    private let api = APIClient.shared
    private let webBaseURL = "https://comms.buildly.io"

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView("Checking integrations…")
                        .tint(ForgeTheme.primary)
                        .frame(maxHeight: .infinity)
                } else {
                    integrationsList
                }
            }
            .background(ForgeTheme.dark900)
            .forgeLogoToolbar(title: "Integrations")
        }
        .task {
            await loadStatus()
        }
    }

    private var integrationsList: some View {
        List {
            if let error {
                Section {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.caption)
                        .listRowBackground(ForgeTheme.dark800)
                }
            }

            // Slack Section
            Section {
                if slackConnected {
                    slackConnectedView
                } else {
                    slackConnectButton
                }
            } header: {
                HStack(spacing: 8) {
                    Image(systemName: "number.square.fill")
                        .foregroundStyle(.purple)
                    Text("Slack")
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
            } footer: {
                Text("Connect Slack to receive DMs and channel messages in ForgeCommunicator.")
                    .foregroundStyle(ForgeTheme.textMuted)
            }

            // Discord Section
            Section {
                if discordConnected {
                    discordConnectedView
                } else {
                    discordConnectButton
                }
            } header: {
                HStack(spacing: 8) {
                    Image(systemName: "gamecontroller.fill")
                        .foregroundStyle(.indigo)
                    Text("Discord")
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
            } footer: {
                Text("Connect Discord to receive DMs and server messages in ForgeCommunicator.")
                    .foregroundStyle(ForgeTheme.textMuted)
            }

            // Integration info
            Section {
                HStack(spacing: 12) {
                    Image(systemName: "info.circle")
                        .foregroundStyle(ForgeTheme.primary)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("How Integrations Work")
                            .font(.body.weight(.medium))
                            .foregroundStyle(.white)
                        Text("Connected services bridge messages into your ForgeCommunicator inbox. DMs and @mentions appear alongside your Forge messages.")
                            .font(.caption)
                            .foregroundStyle(ForgeTheme.textSecondary)
                    }
                }
                .listRowBackground(ForgeTheme.dark800)
            }
        }
        .scrollContentBackground(.hidden)
        .refreshable { await loadStatus() }
    }

    // MARK: - Slack Views

    private var slackConnectButton: some View {
        Button {
            Task { await connectSlack() }
        } label: {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.purple.opacity(0.2))
                        .frame(width: 40, height: 40)
                    Image(systemName: "number.square.fill")
                        .font(.title2)
                        .foregroundStyle(.purple)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("Connect Slack")
                        .font(.body.weight(.medium))
                        .foregroundStyle(.white)
                    Text("Opens Slack's authorization page in your browser")
                        .font(.caption)
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
                Spacer()
                Image(systemName: "arrow.up.right.square")
                    .foregroundStyle(ForgeTheme.primary)
            }
        }
        .listRowBackground(ForgeTheme.dark800)
    }

    private var slackConnectedView: some View {
        Group {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.green.opacity(0.2))
                        .frame(width: 40, height: 40)
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.green)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("Slack Connected")
                        .font(.body.weight(.medium))
                        .foregroundStyle(.white)
                    if !slackWorkspace.isEmpty {
                        Text("Workspace: \(slackWorkspace)")
                            .font(.caption)
                            .foregroundStyle(ForgeTheme.textSecondary)
                    }
                }
                Spacer()
            }
            .listRowBackground(ForgeTheme.dark800)

            Button("Manage on Web") {
                openURL("\(webBaseURL)/profile/integrations")
            }
            .foregroundStyle(ForgeTheme.primary)
            .listRowBackground(ForgeTheme.dark800)

            Button("Disconnect Slack", role: .destructive) {
                Task { await performDisconnectSlack() }
            }
            .listRowBackground(ForgeTheme.dark800)
        }
    }

    // MARK: - Discord Views

    private var discordConnectButton: some View {
        Button {
            Task { await connectDiscord() }
        } label: {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.indigo.opacity(0.2))
                        .frame(width: 40, height: 40)
                    Image(systemName: "gamecontroller.fill")
                        .font(.title2)
                        .foregroundStyle(.indigo)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("Connect Discord")
                        .font(.body.weight(.medium))
                        .foregroundStyle(.white)
                    Text("Opens Discord's authorization page in your browser")
                        .font(.caption)
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
                Spacer()
                Image(systemName: "arrow.up.right.square")
                    .foregroundStyle(ForgeTheme.primary)
            }
        }
        .listRowBackground(ForgeTheme.dark800)
    }

    private var discordConnectedView: some View {
        Group {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.green.opacity(0.2))
                        .frame(width: 40, height: 40)
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.green)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("Discord Connected")
                        .font(.body.weight(.medium))
                        .foregroundStyle(.white)
                    if !discordServer.isEmpty {
                        Text("Server: \(discordServer)")
                            .font(.caption)
                            .foregroundStyle(ForgeTheme.textSecondary)
                    }
                }
                Spacer()
            }
            .listRowBackground(ForgeTheme.dark800)

            Button("Manage on Web") {
                openURL("\(webBaseURL)/profile/integrations")
            }
            .foregroundStyle(ForgeTheme.primary)
            .listRowBackground(ForgeTheme.dark800)

            Button("Disconnect Discord", role: .destructive) {
                Task { await performDisconnectDiscord() }
            }
            .listRowBackground(ForgeTheme.dark800)
        }
    }

    // MARK: - Actions

    private func loadStatus() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let status = try await api.integrationStatus()
            slackConnected = status.slackConnected
            slackWorkspace = status.slackWorkspace ?? ""
            discordConnected = status.discordConnected
            discordServer = status.discordServer ?? ""
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func connectSlack() async {
        do {
            let response = try await api.slackAuthURL()
            openURL(response.url)
        } catch {
            self.error = "Could not get Slack auth URL: \(error.localizedDescription)"
        }
    }

    private func connectDiscord() async {
        do {
            let response = try await api.discordAuthURL()
            openURL(response.url)
        } catch {
            self.error = "Could not get Discord auth URL: \(error.localizedDescription)"
        }
    }

    private func performDisconnectSlack() async {
        do {
            try await api.disconnectSlack()
            slackConnected = false
            slackWorkspace = ""
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func performDisconnectDiscord() async {
        do {
            try await api.disconnectDiscord()
            discordConnected = false
            discordServer = ""
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func openURL(_ urlString: String) {
        guard let url = URL(string: urlString) else { return }
        #if canImport(UIKit)
        UIApplication.shared.open(url)
        #elseif canImport(AppKit)
        NSWorkspace.shared.open(url)
        #endif
    }
}
