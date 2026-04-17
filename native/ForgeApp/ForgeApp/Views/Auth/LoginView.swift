import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authVM: AuthViewModel

    @State private var email = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var isRegistering = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // Logo / brand
            VStack(spacing: 8) {
                Image(systemName: "hammer.fill")
                    .font(.system(size: 48))
                    .foregroundStyle(.blue)
                Text("Forge")
                    .font(.largeTitle.bold())
                Text("Communicator")
                    .font(.title3)
                    .foregroundStyle(.secondary)
            }
            .padding(.bottom, 40)

            // Form
            VStack(spacing: 16) {
                if isRegistering {
                    TextField("Display Name", text: $displayName)
                        .textFieldStyle(.roundedBorder)
                        #if os(iOS)
                        .textContentType(.name)
                        .autocapitalization(.words)
                        #endif
                }

                TextField("Email", text: $email)
                    .textFieldStyle(.roundedBorder)
                    #if os(iOS)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    #endif

                SecureField("Password", text: $password)
                    .textFieldStyle(.roundedBorder)
                    #if os(iOS)
                    .textContentType(isRegistering ? .newPassword : .password)
                    #endif

                if let error = authVM.error {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                }

                Button {
                    Task { await submit() }
                } label: {
                    if authVM.isLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                    } else {
                        Text(isRegistering ? "Create Account" : "Sign In")
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(!isValid || authVM.isLoading)

                Button(isRegistering ? "Already have an account? Sign In" : "Don't have an account? Register") {
                    withAnimation { isRegistering.toggle() }
                    authVM.error = nil
                }
                .font(.callout)
            }
            .frame(maxWidth: 360)
            .padding(.horizontal, 24)

            Spacer()
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        #if os(iOS)
        .background(Color(.systemGroupedBackground))
        #endif
    }

    private var isValid: Bool {
        !email.isEmpty && !password.isEmpty && (!isRegistering || !displayName.isEmpty)
    }

    private func submit() async {
        if isRegistering {
            await authVM.register(email: email, password: password, displayName: displayName)
        } else {
            await authVM.login(email: email, password: password)
        }
    }
}
