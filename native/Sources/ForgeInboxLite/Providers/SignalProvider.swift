import SwiftUI

// Signal's web app (app.signal.org) requires WebRTC, SharedArrayBuffer, and
// Cross-Origin-Opener-Policy — browser APIs that WKWebView does not support.
// The only reliable options are Signal Desktop (if installed) or the system browser.
struct SignalProvider: SourceProvider {
    let type: SourceType = .signal
    let displayName: String = "Signal"

    init(sessionManager: WebSessionManager) {}

    func makeMainView(for source: Source, onProviderConfigUpdate: ((Data?) -> Void)? = nil) -> AnyView {
        AnyView(SignalLaunchView(source: source))
    }
}

private struct SignalLaunchView: View {
    let source: Source

    private let signalDesktopPath = "/Applications/Signal.app"
    private let signalWebURL = URL(string: "https://app.signal.org")!

    private var signalDesktopInstalled: Bool {
        FileManager.default.fileExists(atPath: signalDesktopPath)
    }

    var body: some View {
        VStack(spacing: 28) {
            // Icon
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 52))
                .foregroundStyle(.white.opacity(0.85))

            VStack(spacing: 8) {
                Text("Signal")
                    .font(.title2.bold())
                    .foregroundStyle(.white)

                Text("Signal's web app requires browser APIs (WebRTC, SharedArrayBuffer) that aren't available inside an embedded web view. Use Signal Desktop or open it in your browser.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 380)
            }

            VStack(spacing: 12) {
                if signalDesktopInstalled {
                    Button {
                        launchSignalDesktop()
                    } label: {
                        Label("Open Signal Desktop", systemImage: "arrow.up.forward.app.fill")
                            .frame(maxWidth: 260)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }

                if signalDesktopInstalled {
                    Button {
                        NSWorkspace.shared.open(signalWebURL)
                    } label: {
                        Label("Open in Browser", systemImage: "safari")
                            .frame(maxWidth: 260)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)
                } else {
                    Button {
                        NSWorkspace.shared.open(signalWebURL)
                    } label: {
                        Label("Open in Browser", systemImage: "safari")
                            .frame(maxWidth: 260)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }

                if !signalDesktopInstalled {
                    Link("Download Signal Desktop", destination: URL(string: "https://signal.org/download/")!)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func launchSignalDesktop() {
        switch SignalLauncher.launch(account: source) {
        case .launched: break
        case .signalNotInstalled:
            NSWorkspace.shared.open(URL(string: "https://signal.org/download/")!)
        case .failed(let error):
            print("[SignalProvider] Failed to launch Signal Desktop: \(error)")
        }
    }
}
