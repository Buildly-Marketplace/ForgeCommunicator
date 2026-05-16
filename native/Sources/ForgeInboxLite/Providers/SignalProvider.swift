import SwiftUI
import WebKit

struct SignalProvider: SourceProvider {
    let type: SourceType = .signal
    let displayName: String = "Signal"

    private let sessionManager: WebSessionManager

    init(sessionManager: WebSessionManager) {
        self.sessionManager = sessionManager
    }

    func makeMainView(for source: Source, onProviderConfigUpdate: ((Data?) -> Void)? = nil) -> AnyView {
        let webView = sessionManager.webView(for: source)
        if webView.url == nil {
            webView.load(URLRequest(url: URL(string: "https://web.signal.org")!))
        }

        return AnyView(
            VStack(spacing: 10) {
                HStack(spacing: 10) {
                    Text("Signal Web")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Spacer()
                    Link("Open web.signal.org", destination: URL(string: "https://web.signal.org")!)
                        .font(.caption)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .forgeGlassSurface()

                AccountWebContainerView(webView: webView)
            }
        )
    }
}
