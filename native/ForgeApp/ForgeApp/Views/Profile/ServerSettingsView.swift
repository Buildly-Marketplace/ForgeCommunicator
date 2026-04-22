import SwiftUI
#if canImport(AppKit)
import AppKit
#endif

/// Manage server URL(s). Supports one primary server with optional additional servers.
struct ServerSettingsView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var serverURL: String = ""
    @State private var additionalServers: [String] = []
    @State private var newServerURL: String = ""
    @State private var showAddServer = false
    @State private var errorMessage: String? = nil
    @State private var isSaving = false

    private let defaultServer = "https://comms.buildly.io"

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("The server URL is the base address of your Forge instance. Change this if you self-host or connect to a different server.")
                        .font(.caption)
                        .foregroundStyle(ForgeTheme.textSecondary)
                        .listRowBackground(ForgeTheme.dark800)
                }

                Section("Primary Server") {
                    VStack(alignment: .leading, spacing: 6) {
                        TextField("https://comms.buildly.io", text: $serverURL)
                            .forgeDarkInput()
                            .autocorrectionDisabled()
                            #if os(iOS)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            #endif

                        if let error = errorMessage {
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.red)
                        }
                    }
                    .listRowBackground(ForgeTheme.dark800)

                    Button {
                        applyPrimary()
                    } label: {
                        HStack {
                            if isSaving {
                                ProgressView()
                                    .tint(ForgeTheme.primary)
                                    .padding(.trailing, 4)
                            }
                            Text("Apply & Sign Out")
                                .font(.body.weight(.medium))
                                .foregroundStyle(ForgeTheme.primary)
                        }
                    }
                    .disabled(isSaving)
                    .listRowBackground(ForgeTheme.dark800)

                    if serverURL != defaultServer {
                        Button {
                            serverURL = defaultServer
                            errorMessage = nil
                        } label: {
                            Text("Reset to default (\(defaultServer))")
                                .font(.caption)
                                .foregroundStyle(ForgeTheme.textSecondary)
                        }
                        .listRowBackground(ForgeTheme.dark800)
                    }
                }

                if !additionalServers.isEmpty {
                    Section("Additional Servers") {
                        ForEach(additionalServers, id: \.self) { url in
                            HStack {
                                Image(systemName: "server.rack")
                                    .foregroundStyle(ForgeTheme.textSecondary)
                                Text(url)
                                    .foregroundStyle(.white)
                                    .lineLimit(1)
                                Spacer()
                                Button {
                                    switchTo(url)
                                } label: {
                                    Text("Switch")
                                        .font(.caption.bold())
                                        .foregroundStyle(ForgeTheme.primary)
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background(ForgeTheme.primary.opacity(0.15), in: Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                            .listRowBackground(ForgeTheme.dark800)
                        }
                        .onDelete { indices in
                            additionalServers.remove(atOffsets: indices)
                            saveAdditional()
                        }
                    }
                }

                Section {
                    Button {
                        showAddServer = true
                    } label: {
                        Label("Add Another Server", systemImage: "plus.circle.fill")
                            .foregroundStyle(ForgeTheme.primary)
                    }
                    .listRowBackground(ForgeTheme.dark800)
                }
            }
            .scrollContentBackground(.hidden)
            .background(ForgeTheme.dark900)
            .navigationTitle("Server")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                        .foregroundStyle(ForgeTheme.primary)
                }
            }
            .sheet(isPresented: $showAddServer) {
                addServerSheet
            }
        }
        .onAppear { loadSaved() }
    }

    // MARK: - Add server sheet

    private var addServerSheet: some View {
        NavigationStack {
            List {
                Section {
                    TextField("https://myforge.example.com", text: $newServerURL)
                        .forgeDarkInput()
                        .autocorrectionDisabled()
                        #if os(iOS)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        #endif
                }
                .listRowBackground(ForgeTheme.dark800)
            }
            .scrollContentBackground(.hidden)
            .background(ForgeTheme.dark900)
            .navigationTitle("Add Server")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { showAddServer = false; newServerURL = "" }
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        let trimmed = newServerURL.trimmingCharacters(in: .whitespaces)
                        guard !trimmed.isEmpty, URL(string: trimmed) != nil else { return }
                        if !additionalServers.contains(trimmed) {
                            additionalServers.append(trimmed)
                            saveAdditional()
                        }
                        newServerURL = ""
                        showAddServer = false
                    }
                    .foregroundStyle(ForgeTheme.primary)
                    .disabled(newServerURL.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    // MARK: - Helpers

    private func loadSaved() {
        serverURL = UserDefaults.standard.string(forKey: "serverURL") ?? defaultServer
        additionalServers = UserDefaults.standard.stringArray(forKey: "additionalServers") ?? []
    }

    private func applyPrimary() {
        let trimmed = serverURL.trimmingCharacters(in: .whitespaces)
        guard let url = URL(string: trimmed), trimmed.hasPrefix("http") else {
            errorMessage = "Please enter a valid URL starting with http:// or https://"
            return
        }
        errorMessage = nil
        isSaving = true
        UserDefaults.standard.set(trimmed, forKey: "serverURL")
        Task {
            await APIClient.shared.setBaseURL(url.appendingPathComponent("mobile/v1"))
            await authVM.logout()
            isSaving = false
            dismiss()
        }
    }

    private func switchTo(_ url: String) {
        serverURL = url
        applyPrimary()
    }

    private func saveAdditional() {
        UserDefaults.standard.set(additionalServers, forKey: "additionalServers")
    }
}
