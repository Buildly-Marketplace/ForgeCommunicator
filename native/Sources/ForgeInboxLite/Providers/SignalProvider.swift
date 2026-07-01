import SwiftUI
import WebKit

struct SignalProvider: SourceProvider {
    let type: SourceType = .signal
    let displayName: String = "Signal"

    // Signal's web client requires a Chrome user-agent; Safari/WebKit UA gets blocked.
    private static let signalURL = URL(string: "https://app.signal.org")!
    private static let chromeUA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    private let sessionManager: WebSessionManager

    init(sessionManager: WebSessionManager) {
        self.sessionManager = sessionManager
    }

    func makeMainView(for source: Source, onProviderConfigUpdate: ((Data?) -> Void)? = nil) -> AnyView {
        AnyView(SignalProviderView(source: source, sessionManager: sessionManager))
    }
}

private struct SignalProviderView: View {
    let source: Source
    let sessionManager: WebSessionManager

    var body: some View {
        let webView = sessionManager.webView(for: source)
        AccountWebContainerView(webView: webView)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .onAppear {
                if webView.customUserAgent != SignalProvider.chromeUA {
                    webView.customUserAgent = SignalProvider.chromeUA
                }
                if shouldLoad(webView.url) {
                    webView.load(URLRequest(url: SignalProvider.signalURL))
                }
            }
    }

    private func shouldLoad(_ current: URL?) -> Bool {
        guard let current else { return true }
        return current.host?.contains("signal.org") != true
    }
}
