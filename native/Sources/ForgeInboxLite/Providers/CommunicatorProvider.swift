import SwiftUI
import WebKit

struct CommunicatorProvider: SourceProvider {
    let type: SourceType = .communicator
    let displayName: String = "Communicator"

    private let manager = CommunicatorWebSessionManager.shared

    func makeMainView(for source: Source, onProviderConfigUpdate: ((Data?) -> Void)? = nil) -> AnyView {
        AnyView(CommunicatorSourceView(source: source, manager: manager, onProviderConfigUpdate: onProviderConfigUpdate))
    }
}

private struct CommunicatorSourceView: View {
    let source: Source
    let manager: CommunicatorWebSessionManager
    let onProviderConfigUpdate: ((Data?) -> Void)?

    @State private var serverURLText: String

    init(source: Source, manager: CommunicatorWebSessionManager, onProviderConfigUpdate: ((Data?) -> Void)?) {
        self.source = source
        self.manager = manager
        self.onProviderConfigUpdate = onProviderConfigUpdate
        _serverURLText = State(initialValue: source.communicatorConfig().serverURL)
    }

    var body: some View {
        let webView = manager.webView(for: source)

        VStack(spacing: 10) {
            HStack(spacing: 10) {
                TextField("https://comms.buildly.io", text: $serverURLText)
                    .textFieldStyle(.roundedBorder)

                Button("Connect") {
                    let trimmed = serverURLText.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard let target = workspaceURL(from: trimmed) else { return }
                    let encoded = try? JSONEncoder().encode(CommunicatorSourceConfig(serverURL: trimmed))
                    onProviderConfigUpdate?(encoded)
                    webView.load(URLRequest(url: target))
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(12)
            .forgeGlassSurface()

            VStack(spacing: 0) {
                HStack(spacing: 10) {
                    ForgeBadgeIcon(size: 22)
                    Text("Communicator Workspace")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text("Source-configured session")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

                Divider()

                CommunicatorWebContainerView(webView: webView)
            }
            .forgeGlassSurface()
        }
        .onAppear {
            if webView.url == nil, let target = workspaceURL(from: source.communicatorConfig().serverURL) {
                webView.load(URLRequest(url: target))
            }
        }
    }

    private func workspaceURL(from value: String) -> URL? {
        var base = value
        if !base.hasPrefix("http://") && !base.hasPrefix("https://") {
            base = "https://\(base)"
        }

        guard var components = URLComponents(string: base) else {
            return nil
        }

        if components.path.isEmpty || components.path == "/" {
            components.path = "/workspaces"
        }

        return components.url
    }
}

private final class CommunicatorWebSessionManager {
    static let shared = CommunicatorWebSessionManager()

    private var webViews: [UUID: WKWebView] = [:]
    private var notificationTrackers: [UUID: CommunicatorTitleNotificationTracker] = [:]

    func webView(for source: Source) -> WKWebView {
        if let existing = webViews[source.id] {
            return existing
        }

        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.preferredContentMode = .desktop
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = true
        configuration.preferences.isTextInteractionEnabled = true

        let view = WKWebView(frame: .zero, configuration: configuration)
        view.allowsBackForwardNavigationGestures = true
        view.allowsMagnification = true

        notificationTrackers[source.id] = CommunicatorTitleNotificationTracker(
            source: source,
            webView: view
        )

        webViews[source.id] = view
        return view
    }
}

private struct CommunicatorWebContainerView: NSViewRepresentable {
    let webView: WKWebView

    func makeNSView(context: Context) -> WebViewHostContainer {
        let container = WebViewHostContainer()
        container.host(webView)
        return container
    }

    func updateNSView(_ nsView: WebViewHostContainer, context: Context) {
        nsView.host(webView)
    }
}

private final class CommunicatorTitleNotificationTracker {
    private let source: Source
    private var titleObservation: NSKeyValueObservation?
    private var urlObservation: NSKeyValueObservation?
    private var lastUnreadCount = 0
    private var lastDeliveredTitle = ""
    private var lastDeliveryDate = Date.distantPast

    init(source: Source, webView: WKWebView) {
        self.source = source

        titleObservation = webView.observe(\.title, options: [.new]) { [weak self] view, _ in
            self?.handleChange(title: view.title ?? "", url: view.url)
        }

        urlObservation = webView.observe(\.url, options: [.new]) { [weak self] view, _ in
            self?.handleChange(title: view.title ?? "", url: view.url)
        }
    }

    private func handleChange(title: String, url: URL?) {
        let unread = unreadCount(from: title)

        if unread == 0 {
            lastUnreadCount = 0
            return
        }

        let now = Date()
        let didIncrease = unread > lastUnreadCount
        let didChangeTitle = title != lastDeliveredTitle
        let cooldownElapsed = now.timeIntervalSince(lastDeliveryDate) > 30

        guard didIncrease || (didChangeTitle && cooldownElapsed) else {
            lastUnreadCount = unread
            return
        }

        lastUnreadCount = unread
        lastDeliveredTitle = title
        lastDeliveryDate = now

        let cleaned = title.replacingOccurrences(
            of: "^\\(\\d+\\)\\s*",
            with: "",
            options: .regularExpression
        )
        let body = cleaned.isEmpty ? "New message activity on \(url?.host ?? "Communicator")." : cleaned

        NotificationService.postSourceActivity(
            sourceID: source.id,
            sourceName: source.displayName,
            providerName: "Communicator",
            body: body,
            dedupeHint: "title:\(unread):\(body)"
        )
    }

    private func unreadCount(from title: String) -> Int {
        guard let regex = try? NSRegularExpression(pattern: "^\\((\\d+)\\)", options: []) else {
            return 0
        }

        let range = NSRange(title.startIndex..<title.endIndex, in: title)
        guard
            let match = regex.firstMatch(in: title, options: [], range: range),
            let countRange = Range(match.range(at: 1), in: title),
            let count = Int(title[countRange])
        else {
            return 0
        }

        return count
    }
}
