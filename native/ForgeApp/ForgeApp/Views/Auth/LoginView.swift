import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authVM: AuthViewModel

    @State private var email = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var isRegistering = false
    @State private var serverURL: String = UserDefaults.standard.string(forKey: "serverURL") ?? "https://comms.buildly.io"
    @State private var showServerConfig = false

    private let api = APIClient.shared

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                Spacer(minLength: 40)

                // MARK: - Logo & Branding (matches web splash)
                VStack(spacing: 12) {
                    ForgeLogoImage(size: 72)
                        .shadow(color: ForgeTheme.primary.opacity(0.4), radius: 12, y: 4)

                    Text("ForgeCommunicator")
                        .font(.system(size: 28, weight: .bold, design: .default))
                        .foregroundStyle(.white)
                        .shadow(color: ForgeTheme.primary.opacity(0.5), radius: 20)

                    Text("Connect. Collaborate. Create.")
                        .font(.system(size: 16, weight: .light))
                        .foregroundStyle(ForgeTheme.primary.opacity(0.8))
                        .tracking(1)
                }
                .padding(.bottom, 36)

                // MARK: - Server configuration
                VStack(spacing: 0) {
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            showServerConfig.toggle()
                        }
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "server.rack")
                                .font(.caption)
                                .foregroundStyle(ForgeTheme.primary)
                            Text("Connect to a Server")
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(ForgeTheme.textSecondary)
                            Spacer()
                            Image(systemName: showServerConfig ? "chevron.up" : "chevron.down")
                                .font(.caption2)
                                .foregroundStyle(ForgeTheme.textMuted)
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    }

                    if showServerConfig {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Enter the URL of your ForgeCommunicator server. Ask your team admin if you're unsure.")
                                .font(.caption)
                                .foregroundStyle(ForgeTheme.textMuted)

                            TextField("https://comms.example.com", text: $serverURL)
                                .forgeDarkInput()
                                #if os(iOS)
                                .keyboardType(.URL)
                                .autocapitalization(.none)
                                .textContentType(.URL)
                                #endif
                                .onChange(of: serverURL) { _, newValue in
                                    applyServerURL(newValue)
                                }

                            HStack(spacing: 6) {
                                Image(systemName: serverURLValid ? "checkmark.circle.fill" : "exclamationmark.circle")
                                    .font(.caption)
                                    .foregroundStyle(serverURLValid ? .green : .orange)
                                Text(serverURLValid ? "Server URL set" : "Enter a valid https:// URL")
                                    .font(.caption)
                                    .foregroundStyle(serverURLValid ? .green : .orange)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.bottom, 12)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                }
                .background(ForgeTheme.dark800.opacity(0.6))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.white.opacity(0.06), lineWidth: 1)
                )
                .frame(maxWidth: 380)
                .padding(.horizontal, 20)
                .padding(.bottom, 16)

                // MARK: - Glass form panel (matches web login-form-panel)
                VStack(spacing: 20) {
                    Text(isRegistering ? "Create Account" : "Welcome Back")
                        .font(.title2.bold())
                        .foregroundStyle(.white)

                    Text(isRegistering
                         ? "Join your team on ForgeCommunicator"
                         : "Sign in to continue your conversations")
                        .font(.subheadline)
                        .foregroundStyle(ForgeTheme.textSecondary)
                        .multilineTextAlignment(.center)

                    // Divider
                    Rectangle()
                        .fill(Color.white.opacity(0.08))
                        .frame(height: 1)
                        .padding(.vertical, 4)

                    // Form fields
                    VStack(spacing: 14) {
                        if isRegistering {
                            TextField("Display Name", text: $displayName)
                                .forgeDarkInput()
                                #if os(iOS)
                                .textContentType(.name)
                                .autocapitalization(.words)
                                #endif
                        }

                        TextField("Email address", text: $email)
                            .forgeDarkInput()
                            #if os(iOS)
                            .textContentType(.emailAddress)
                            .keyboardType(.emailAddress)
                            .autocapitalization(.none)
                            #endif

                        SecureField("Password", text: $password)
                            .forgeDarkInput()
                            #if os(iOS)
                            .textContentType(isRegistering ? .newPassword : .password)
                            #endif
                    }

                    if let error = authVM.error {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.caption)
                            Text(error)
                                .font(.caption)
                        }
                        .foregroundStyle(.red.opacity(0.9))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.red.opacity(0.12))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.red.opacity(0.25), lineWidth: 1)
                        )
                    }

                    // Submit button (matches web blue-600 button)
                    Button {
                        Task { await submit() }
                    } label: {
                        Group {
                            if authVM.isLoading {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Text(isRegistering ? "Create Account" : "Sign In")
                                    .font(.body.weight(.semibold))
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(
                            isValid && !authVM.isLoading
                                ? ForgeTheme.primary
                                : ForgeTheme.primary.opacity(0.4)
                        )
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(!isValid || authVM.isLoading)

                    // Toggle login / register
                    Button {
                        withAnimation(.easeInOut(duration: 0.25)) { isRegistering.toggle() }
                        authVM.error = nil
                    } label: {
                        Group {
                            if isRegistering {
                                Text("Already have an account? ") +
                                Text("Sign In").foregroundColor(ForgeTheme.primary)
                            } else {
                                Text("Don't have an account? ") +
                                Text("Sign up for free").foregroundColor(ForgeTheme.primary)
                            }
                        }
                        .font(.callout)
                        .foregroundStyle(ForgeTheme.textSecondary)
                    }
                }
                .padding(24)
                .forgeGlassPanel()
                .frame(maxWidth: 380)
                .padding(.horizontal, 20)

                // Footer tagline
                Text("Start Your Next Conversation")
                    .font(.caption)
                    .foregroundStyle(ForgeTheme.textMuted)
                    .padding(.top, 24)

                Spacer(minLength: 40)
            }
            .frame(maxWidth: .infinity)
        }
        .background(ForgeTheme.backgroundGradient.ignoresSafeArea())
        #if os(iOS)
        .preferredColorScheme(.dark)
        #endif
    }

    private var isValid: Bool {
        !email.isEmpty && !password.isEmpty && (!isRegistering || !displayName.isEmpty)
    }

    private var serverURLValid: Bool {
        guard let url = URL(string: serverURL),
              let scheme = url.scheme,
              scheme == "https",
              url.host != nil else { return false }
        return true
    }

    private func applyServerURL(_ urlString: String) {
        let trimmed = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let base = URL(string: trimmed),
              base.scheme == "https",
              base.host != nil else { return }
        let apiURL = base.appendingPathComponent("mobile/v1")
        Task {
            await api.setBaseURL(apiURL)
        }
        UserDefaults.standard.set(trimmed, forKey: "serverURL")
    }

    private func submit() async {
        applyServerURL(serverURL)
        if isRegistering {
            await authVM.register(email: email, password: password, displayName: displayName)
        } else {
            await authVM.login(email: email, password: password)
        }
    }
}
