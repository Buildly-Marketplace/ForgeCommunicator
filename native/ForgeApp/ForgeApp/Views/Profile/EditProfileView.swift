import SwiftUI

struct EditProfileView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var displayName: String = ""
    @State private var bio: String = ""
    @State private var title: String = ""
    @State private var phone: String = ""
    @State private var avatarUrl: String = ""
    @State private var githubUrl: String = ""
    @State private var linkedinUrl: String = ""
    @State private var isSaving = false
    @State private var error: String?

    private let api = APIClient.shared

    var body: some View {
        NavigationStack {
            List {
                // Avatar section
                Section {
                    HStack {
                        Spacer()
                        VStack(spacing: 12) {
                            if let user = authVM.currentUser {
                                AvatarView(user: user, size: 80)
                            }
                            TextField("Avatar URL", text: $avatarUrl)
                                .forgeDarkInput()
                                .font(.caption)
                                #if os(iOS)
                                .keyboardType(.URL)
                                .autocapitalization(.none)
                                #endif
                        }
                        Spacer()
                    }
                    .listRowBackground(ForgeTheme.dark800)
                }

                Section("Display Name") {
                    TextField("Your name", text: $displayName)
                        .forgeDarkInput()
                        #if os(iOS)
                        .textContentType(.name)
                        #endif
                        .listRowBackground(ForgeTheme.dark800)
                }

                Section("Title") {
                    TextField("e.g. Software Engineer", text: $title)
                        .forgeDarkInput()
                        .listRowBackground(ForgeTheme.dark800)
                }

                Section("Bio") {
                    TextField("Tell us about yourself", text: $bio, axis: .vertical)
                        .forgeDarkInput()
                        .lineLimit(3...6)
                        .listRowBackground(ForgeTheme.dark800)
                }

                Section("Phone") {
                    TextField("Phone number", text: $phone)
                        .forgeDarkInput()
                        #if os(iOS)
                        .keyboardType(.phonePad)
                        .textContentType(.telephoneNumber)
                        #endif
                        .listRowBackground(ForgeTheme.dark800)
                }

                Section("GitHub") {
                    TextField("https://github.com/username", text: $githubUrl)
                        .forgeDarkInput()
                        #if os(iOS)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .textContentType(.URL)
                        #endif
                        .listRowBackground(ForgeTheme.dark800)
                }

                Section("LinkedIn") {
                    TextField("https://linkedin.com/in/username", text: $linkedinUrl)
                        .forgeDarkInput()
                        #if os(iOS)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .textContentType(.URL)
                        #endif
                        .listRowBackground(ForgeTheme.dark800)
                }

                if let error {
                    Section {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                            .listRowBackground(ForgeTheme.dark800)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(ForgeTheme.dark900)
            .navigationTitle("Edit Profile")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(ForgeTheme.textSecondary)
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isSaving {
                        ProgressView()
                    } else {
                        Button("Save") {
                            Task { await save() }
                        }
                        .disabled(displayName.trimmingCharacters(in: .whitespaces).isEmpty)
                        .foregroundStyle(ForgeTheme.primary)
                    }
                }
            }
        }
        #if os(macOS)
        .frame(minWidth: 460, idealWidth: 520, minHeight: 620)
        #endif
        .onAppear {
            if let user = authVM.currentUser {
                displayName = user.displayName
                bio = user.bio ?? ""
                title = user.title ?? ""
                phone = user.phone ?? ""
                avatarUrl = user.avatarUrl ?? ""
                githubUrl = user.githubUrl ?? ""
                linkedinUrl = user.linkedinUrl ?? ""
            }
        }
    }

    private func save() async {
        isSaving = true
        error = nil
        defer { isSaving = false }

        var update = ProfileUpdate()
        update.displayName = displayName.trimmingCharacters(in: .whitespaces)
        update.bio = bio.isEmpty ? nil : bio
        update.title = title.isEmpty ? nil : title
        update.phone = phone.isEmpty ? nil : phone
        update.avatarUrl = avatarUrl.isEmpty ? nil : avatarUrl
        update.githubUrl = githubUrl.isEmpty ? nil : githubUrl
        update.linkedinUrl = linkedinUrl.isEmpty ? nil : linkedinUrl

        do {
            let updated = try await api.updateProfile(update)
            authVM.currentUser = updated
            dismiss()
        } catch {
            self.error = "Failed to save: \(error.localizedDescription)"
        }
    }
}

