import SwiftUI
import WebKit

struct WhatsAppProvider: SourceProvider {
    let type: SourceType = .whatsapp
    let displayName: String = "WhatsApp"

    private let sessionManager: WebSessionManager

    init(sessionManager: WebSessionManager) {
        self.sessionManager = sessionManager
    }

    func makeMainView(for source: Source, onProviderConfigUpdate: ((Data?) -> Void)? = nil) -> AnyView {
        let webView = sessionManager.webView(for: source)
        if webView.url == nil {
            webView.load(URLRequest(url: URL(string: "https://web.whatsapp.com")!))
        }

        return AnyView(AccountWebContainerView(webView: webView))
    }
}
