import SwiftUI
import WebKit

struct ForgeCommunicatorShellView: View {
    private enum TopLevelDestination {
        case nativeCommunicator
        case sources
    }

    @StateObject private var store = AccountStore()
    @State private var webSessionManager = WebSessionManager()
    @State private var showingAddSheet = false
    @State private var destination: TopLevelDestination = .nativeCommunicator

    var body: some View {
        ZStack {
            ForgeBackgroundLayer()

            HStack(spacing: 0) {
                ZStack {
                    SidebarStarfieldBackground()

                    VStack(spacing: 0) {
                        sidebarHeader
                        topLevelNav

                        if destination == .sources {
                            List {
                                ForEach(store.sources) { source in
                                    Button {
                                        store.selectAccount(id: source.id)
                                    } label: {
                                        sourceRow(source)
                                    }
                                    .buttonStyle(.plain)
                                    .listRowBackground(Color.clear)
                                    .listRowSeparator(.hidden)
                                    .listRowInsets(EdgeInsets(top: 4, leading: 10, bottom: 4, trailing: 10))
                                    .contextMenu {
                                        Button("Rename") {
                                            // Rename flow lands in next pass.
                                        }
                                        if source.type == .telegram {
                                            Button("Reset Telegram Session", role: .destructive) {
                                                resetWebSession(for: source)
                                            }
                                        }
                                        Button("Remove", role: .destructive) {
                                            store.removeAccount(id: source.id)
                                        }
                                    }
                                }
                            }
                            .scrollContentBackground(.hidden)
                            .listStyle(.plain)
                            .foregroundStyle(.white)
                        }

                        Spacer(minLength: 0)
                    }
                }
                .frame(minWidth: 280, idealWidth: 320, maxWidth: 360)

                Rectangle()
                    .fill(Color.white.opacity(0.10))
                    .frame(width: 1)

                ZStack {
                    communicatorWorkspacePane
                        .opacity(destination == .nativeCommunicator ? 1 : 0)
                        .allowsHitTesting(destination == .nativeCommunicator)

                    sourcesWorkspacePane
                        .opacity(destination == .sources ? 1 : 0)
                        .allowsHitTesting(destination == .sources)
                }
                .padding(10)
                .foregroundStyle(.white)
                .background(ForgeTheme.dark950)
            }
            .tint(ForgeTheme.primary)
        }
        .preferredColorScheme(.dark)
        .sheet(isPresented: $showingAddSheet) {
            AddAccountSheet(mode: .add) { type, name in
                store.addSource(type: type, displayName: name)
            }
        }
        .onAppear {
            store.load()
        }
        .onChange(of: destination) { next in
            guard next == .sources else { return }
            if store.selectedSource == nil, let first = store.sources.first {
                store.selectAccount(id: first.id)
            }
        }
    }

    @ViewBuilder
    private var communicatorWorkspacePane: some View {
        nativeCommunicatorPane
    }

    @ViewBuilder
    private var nativeCommunicatorPane: some View {
        if let communicator = primaryCommunicatorSource {
            NativeCommunicatorHomeView(
                source: communicator,
                onProviderConfigUpdate: { encoded in
                    store.updateSourceProviderConfig(id: communicator.id, providerConfig: encoded)
                }
            )
            .id("native-communicator-\(communicator.id.uuidString)")
        } else {
            VStack(spacing: 16) {
                ForgeLogoIcon(size: 46)

                Text("No Forge server configured")
                    .font(.headline)
                    .foregroundStyle(.white)

                Text("Add your first Forge server source to enable the native Communicator home.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                Button("Add Forge Server") {
                    showingAddSheet = true
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(24)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .forgeGlassSurface()
        }
    }

    private var sourcesManagerPane: some View {
        VStack(spacing: 10) {
            ForgeHeaderBar(title: "Sources", subtitle: "Manage Forge servers and providers")
            VStack(alignment: .leading, spacing: 14) {
                Text("Configured Sources")
                    .font(.headline)
                    .foregroundStyle(.white)

                Text("Use the sidebar to select, rename, and remove sources. To add a new source, use the plus icon in the top header.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                if store.sources.isEmpty {
                    Text("No sources configured yet.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    VStack(spacing: 8) {
                        ForEach(store.sources) { source in
                            HStack(spacing: 10) {
                                Image(systemName: iconName(for: source.type))
                                    .foregroundStyle(iconColor(for: source.type))
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(source.displayName)
                                        .foregroundStyle(.white)
                                    Text(source.type.displayLabel)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer(minLength: 0)
                            }
                            .padding(.horizontal, 10)
                            .padding(.vertical, 8)
                            .background(
                                RoundedRectangle(cornerRadius: 10, style: .continuous)
                                    .fill(ForgeTheme.overlayFill.opacity(0.72))
                            )
                        }
                    }
                }

                Spacer(minLength: 0)
            }
            .padding(18)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .forgeGlassSurface()
        }
    }

    @ViewBuilder
    private var sourcesWorkspacePane: some View {
        if let source = store.selectedSource ?? store.sources.first {
            VStack(spacing: 10) {
                ForgeHeaderBar(title: source.displayName, subtitle: "\(source.type.displayLabel) • Source")
                providerView(for: source)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .id("sources-workspace-\(source.id.uuidString)")
            .onAppear {
                if store.selectedSourceID != source.id {
                    store.selectAccount(id: source.id)
                }
            }
        } else {
            sourcesManagerPane
        }
    }

    private var primaryCommunicatorSource: Source? {
        if let selected = store.selectedSource, selected.type == .communicator {
            return selected
        }
        return store.sources.first(where: { $0.type == .communicator })
    }

    @ViewBuilder
    private func providerView(for source: Source) -> some View {
        switch source.type {
        case .communicator:
            CommunicatorProvider().makeMainView(
                for: source,
                onProviderConfigUpdate: { encoded in
                    store.updateSourceProviderConfig(id: source.id, providerConfig: encoded)
                }
            )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .forgeGlassSurface()
        case .whatsapp:
            WhatsAppProvider(sessionManager: webSessionManager).makeMainView(for: source, onProviderConfigUpdate: nil)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .forgeGlassSurface()
        case .signal:
            SignalProvider(sessionManager: webSessionManager).makeMainView(for: source, onProviderConfigUpdate: nil)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .forgeGlassSurface()
        case .telegram:
            TelegramProviderView(source: source, sessionManager: webSessionManager)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .forgeGlassSurface()
        }
    }

    @ViewBuilder
    private func sourceRow(_ source: Source) -> some View {
        let selected = store.selectedSourceID == source.id

        HStack(spacing: 10) {
            Image(systemName: iconName(for: source.type))
                .foregroundStyle(iconColor(for: source.type))
                .font(.system(size: 14, weight: .semibold))
                .frame(width: 22)

            VStack(alignment: .leading, spacing: 1) {
                Text(source.displayName)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 9)
        .background(
            RoundedRectangle(cornerRadius: 11, style: .continuous)
                .fill(selected ? ForgeTheme.primary.opacity(0.14) : ForgeTheme.overlayFill)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 11, style: .continuous)
                .stroke(selected ? ForgeTheme.glassBorderActive : ForgeTheme.glassBorder, lineWidth: 1)
        )
        .shadow(color: selected ? ForgeTheme.primary.opacity(0.20) : .clear, radius: 8, x: 0, y: 3)
    }

    private func iconName(for type: SourceType) -> String {
        switch type {
        case .communicator:
            return "waveform"
        case .whatsapp:
            return "bubble.left"
        case .signal:
            return "dot.radiowaves.left.and.right"
        case .telegram:
            return "paperplane"
        }
    }

    private func iconColor(for type: SourceType) -> Color {
        switch type {
        case .communicator:
            return ForgeTheme.primary
        case .whatsapp:
            return .green
        case .signal:
            return ForgeTheme.amber
        case .telegram:
            return .cyan
        }
    }

    private var sidebarHeader: some View {
        HStack(spacing: 10) {
            Button {
                destination = .nativeCommunicator
            } label: {
                ForgeLogoIcon(size: 30)
            }
            .buttonStyle(.plain)

            Spacer()

            Button {
                showingAddSheet = true
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 26, height: 26)
                    .background(
                        Circle()
                            .fill(Color.white.opacity(0.10))
                    )
                    .overlay(
                        Circle()
                            .stroke(Color.white.opacity(0.18), lineWidth: 1)
                    )
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(ForgeTheme.dark950)
        .overlay(Rectangle().fill(ForgeTheme.glassBorder).frame(height: 1), alignment: .bottom)
    }

    private var topLevelNav: some View {
        VStack(spacing: 8) {
            topLevelButton(
                title: "Communicator",
                systemImage: "waveform",
                isSelected: destination == .nativeCommunicator
            ) {
                destination = .nativeCommunicator
            }

            topLevelButton(
                title: "Sources",
                systemImage: "square.stack.3d.up.fill",
                isSelected: destination == .sources
            ) {
                destination = .sources
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 10)
        .background(ForgeTheme.dark950.opacity(0.88))
        .overlay(Rectangle().fill(ForgeTheme.glassBorder).frame(height: 1), alignment: .bottom)
    }

    private func topLevelButton(title: String, systemImage: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: systemImage)
                    .font(.system(size: 13, weight: .semibold))
                    .frame(width: 20)
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                Spacer(minLength: 0)
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(isSelected ? ForgeTheme.primary.opacity(0.14) : ForgeTheme.overlayFill.opacity(0.74))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(isSelected ? ForgeTheme.glassBorderActive : ForgeTheme.glassBorder, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private func resetWebSession(for source: Source) {
        webSessionManager.removeWebsiteData(for: source) {
            if store.selectedSourceID == source.id {
                store.selectAccount(id: source.id)
            }
        }
    }

}

private struct TelegramProviderView: View {
    let source: Source
    let sessionManager: WebSessionManager

    private let telegramDesktopURL = URL(string: "https://web.telegram.org/k/")!
    private let telegramDesktopUserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    var body: some View {
        let webView = sessionManager.webView(for: source)

        AccountWebContainerView(webView: webView)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .onAppear {
                if webView.customUserAgent != telegramDesktopUserAgent {
                    webView.customUserAgent = telegramDesktopUserAgent
                }

                if shouldForceTelegramDesktopLoad(webView.url) {
                    webView.load(URLRequest(url: telegramDesktopURL))
                }
            }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func shouldForceTelegramDesktopLoad(_ currentURL: URL?) -> Bool {
        guard let currentURL else { return true }
        guard let host = currentURL.host?.lowercased(), host.contains("telegram.org") else {
            return true
        }
        return !currentURL.path.hasPrefix("/k/")
    }
}

private struct SidebarStarfieldBackground: View {
    private let stars: [CGPoint] = [
        CGPoint(x: 0.05, y: 0.08), CGPoint(x: 0.13, y: 0.22), CGPoint(x: 0.18, y: 0.47),
        CGPoint(x: 0.24, y: 0.14), CGPoint(x: 0.33, y: 0.36), CGPoint(x: 0.42, y: 0.19),
        CGPoint(x: 0.51, y: 0.28), CGPoint(x: 0.63, y: 0.11), CGPoint(x: 0.72, y: 0.40),
        CGPoint(x: 0.81, y: 0.24), CGPoint(x: 0.91, y: 0.15), CGPoint(x: 0.12, y: 0.67),
        CGPoint(x: 0.27, y: 0.74), CGPoint(x: 0.39, y: 0.83), CGPoint(x: 0.58, y: 0.72),
        CGPoint(x: 0.74, y: 0.80), CGPoint(x: 0.88, y: 0.64)
    ]

    var body: some View {
        ZStack {
            ForgeTheme.dark950

            GeometryReader { proxy in
                ZStack {
                    ForEach(stars.indices, id: \.self) { index in
                        Circle()
                            .fill(Color.white.opacity(index.isMultiple(of: 3) ? 0.44 : 0.26))
                            .frame(width: index.isMultiple(of: 4) ? 2.0 : 1.4, height: index.isMultiple(of: 4) ? 2.0 : 1.4)
                            .position(
                                x: stars[index].x * proxy.size.width,
                                y: stars[index].y * proxy.size.height
                            )
                    }
                }
            }
            .allowsHitTesting(false)
        }
        .ignoresSafeArea()
    }
}
