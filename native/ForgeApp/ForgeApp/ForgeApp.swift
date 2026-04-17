import SwiftUI

@main
struct ForgeApp: App {
    @StateObject private var authVM = AuthViewModel()
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(authVM)
                .environmentObject(appState)
        }
        #if os(macOS)
        .defaultSize(width: 900, height: 700)
        #endif
    }
}

struct RootView: View {
    @EnvironmentObject var authVM: AuthViewModel

    var body: some View {
        Group {
            if authVM.isAuthenticated {
                MainTabView()
            } else {
                LoginView()
            }
        }
        .animation(.easeInOut, value: authVM.isAuthenticated)
        .task {
            await authVM.restoreSession()
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            ConversationListView()
                .tabItem {
                    Label("Messages", systemImage: "message.fill")
                }

            ContactListView()
                .tabItem {
                    Label("Contacts", systemImage: "person.2.fill")
                }

            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person.crop.circle.fill")
                }
        }
        #if os(macOS)
        .frame(minWidth: 600, minHeight: 400)
        #endif
    }
}
