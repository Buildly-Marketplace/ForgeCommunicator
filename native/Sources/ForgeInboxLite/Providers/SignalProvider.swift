import SwiftUI
import WebKit

struct SignalProvider: SourceProvider {
    let type: SourceType = .signal
    let displayName: String = "Signal"

    private let sessionManager: SignalWebSessionManager

    init(sessionManager: WebSessionManager) {
        // Signal needs its own session manager that sets the Chrome UA at
        // WKWebViewConfiguration time — setting customUserAgent after creation
        // is too late when a cached webview already has the wrong UA.
        self.sessionManager = SignalWebSessionManager.shared
    }

    func makeMainView(for source: Source, onProviderConfigUpdate: ((Data?) -> Void)? = nil) -> AnyView {
        AnyView(SignalProviderView(source: source, sessionManager: sessionManager))
    }
}

// Dedicated session manager for Signal that builds WKWebViews with a Chrome UA
// baked into the configuration before first load.
private final class SignalWebSessionManager {
    static let shared = SignalWebSessionManager()

    private static let signalURL = URL(string: "https://app.signal.org")!
    // Signal's web app blocks Safari/WebKit UA — requires Chrome UA to load.
    private static let chromeUA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    private var webViews: [UUID: WKWebView] = [:]

    func webView(for source: Source) -> WKWebView {
        if let existing = webViews[source.id] {
            return existing
        }

        let config = WKWebViewConfiguration()
        if #available(macOS 14.0, *) {
            config.websiteDataStore = WKWebsiteDataStore(forIdentifier: source.id)
        } else {
            config.websiteDataStore = .nonPersistent()
        }
        config.defaultWebpagePreferences.preferredContentMode = .desktop
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        config.preferences.javaScriptCanOpenWindowsAutomatically = true
        config.preferences.isTextInteractionEnabled = true

        let view = WKWebView(frame: .zero, configuration: config)
        view.allowsBackForwardNavigationGestures = true
        view.allowsMagnification = true
        // Set Chrome UA on the configuration level before any load.
        view.customUserAgent = Self.chromeUA

        view.load(URLRequest(url: Self.signalURL))

        webViews[source.id] = view
        return view
    }
}

private struct SignalProviderView: View {
    let source: Source
    let sessionManager: SignalWebSessionManager

    var body: some View {
        let webView = sessionManager.webView(for: source)
        AccountWebContainerView(webView: webView)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
