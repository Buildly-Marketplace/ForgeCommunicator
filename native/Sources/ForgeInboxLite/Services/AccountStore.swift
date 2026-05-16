import Foundation

@MainActor
final class AccountStore: ObservableObject {
    @Published private(set) var accounts: [Account] = []
    @Published var selectedAccountID: UUID?
    @Published var lastError: String?

    private let configStore: EncryptedConfigStore
    private let fileManager = FileManager.default

    init(configStore: EncryptedConfigStore = EncryptedConfigStore()) {
        self.configStore = configStore
    }

    func load() {
        Task {
            do {
                let config = try await configStore.load()
                let loaded = config.accounts
                self.accounts = loaded
                    .enumerated()
                    .map { index, account in
                        var mutable = account
                        if mutable.sortOrder == nil {
                            mutable.sortOrder = index
                        }
                        return mutable
                    }
                    .sorted { ($0.sortOrder ?? 0) < ($1.sortOrder ?? 0) }

                self.selectedAccountID = config.selectedAccountID ?? self.accounts.first?.id
            } catch {
                self.accounts = []
                self.selectedAccountID = nil
                print("Failed to load config: \(error)")
            }
        }
    }

    var sources: [Source] { accounts }

    var selectedSourceID: UUID? {
        get { selectedAccountID }
        set { selectedAccountID = newValue }
    }

    var selectedSource: Source? { selectedAccount }

    func addSource(type: SourceType, displayName: String) {
        addAccount(type: type, displayName: displayName)
    }

    var selectedAccount: Account? {
        guard let selectedAccountID else { return nil }
        return accounts.first(where: { $0.id == selectedAccountID })
    }

    func addAccount(type: AccountType, displayName: String) {
        Task {
            do {
                let profilesRoot = try await configStore.profilesRootURL()
                let accountID = UUID()
                let accountProfile = profilesRoot.appendingPathComponent(accountID.uuidString, isDirectory: true)
                try fileManager.createDirectory(at: accountProfile, withIntermediateDirectories: true)

                let account = Account(
                    id: accountID,
                    type: type,
                    displayName: displayName,
                    profilePath: accountProfile.path,
                    createdAt: Date(),
                    lastOpenedAt: nil,
                    providerConfig: type == .communicator ? (try? JSONEncoder().encode(CommunicatorSourceConfig.default)) : nil,
                    sortOrder: accounts.count
                )

                accounts.append(account)
                selectedAccountID = account.id
                await persist()
            } catch {
                print("[ForgeInbox] Failed to add account: \(error)")
                await MainActor.run { self.lastError = error.localizedDescription }
            }
        }
    }

    func renameAccount(id: UUID, newName: String) {
        guard let index = accounts.firstIndex(where: { $0.id == id }) else { return }
        accounts[index].displayName = newName
        Task { await persist() }
    }

    func removeAccount(id: UUID) {
        guard let index = accounts.firstIndex(where: { $0.id == id }) else { return }
        let removed = accounts.remove(at: index)

        if selectedAccountID == id {
            selectedAccountID = accounts.first?.id
        }

        do {
            if fileManager.fileExists(atPath: removed.profilePath) {
                try fileManager.removeItem(atPath: removed.profilePath)
            }
        } catch {
            print("Failed to remove profile directory: \(error)")
        }

        Task { await persist() }
    }

    func moveAccounts(from source: IndexSet, to destination: Int) {
        accounts.move(fromOffsets: source, toOffset: destination)
        for index in accounts.indices {
            accounts[index].sortOrder = index
        }
        Task { await persist() }
    }

    func selectAccount(id: UUID) {
        selectedAccountID = id
        guard let index = accounts.firstIndex(where: { $0.id == id }) else { return }
        accounts[index].lastOpenedAt = Date()
        Task { await persist() }
    }

    func updateSourceProviderConfig(id: UUID, providerConfig: Data?) {
        guard let index = accounts.firstIndex(where: { $0.id == id }) else { return }
        accounts[index].providerConfig = providerConfig
        Task { await persist() }
    }

    func updateCommunicatorServerURL(id: UUID, serverURL: String) {
        guard let index = accounts.firstIndex(where: { $0.id == id }) else { return }

        let normalized = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }

        let config = accounts[index].communicatorConfig()
        let next = CommunicatorSourceConfig(serverURL: normalized)
        guard config != next else { return }

        accounts[index].providerConfig = try? JSONEncoder().encode(next)
        Task { await persist() }
    }

    private func persist() async {
        let config = PersistedConfig(schemaVersion: 2, sources: accounts, selectedSourceID: selectedAccountID)
        do {
            try await configStore.save(config)
        } catch {
            print("Failed to persist config: \(error)")
        }
    }
}
