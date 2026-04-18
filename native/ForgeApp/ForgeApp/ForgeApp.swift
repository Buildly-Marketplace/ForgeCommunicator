import SwiftUI
import UserNotifications

@main
struct ForgeApp: App {
    @StateObject private var authVM = AuthViewModel()
    @StateObject private var appState = AppState()
    @StateObject private var notificationService = NotificationService.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(authVM)
                .environmentObject(appState)
                .environmentObject(notificationService)
                .preferredColorScheme(.dark)
                .task {
                    await notificationService.requestPermission()
                }
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
    @EnvironmentObject var notificationService: NotificationService

    var body: some View {
        TabView {
            ConversationListView()
                .tabItem {
                    Label("Messages", systemImage: "message.fill")
                }
                .badge(notificationService.unreadCount)

            ContactListView()
                .tabItem {
                    Label("Contacts", systemImage: "person.2.fill")
                }

            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person.crop.circle.fill")
                }
        }
        .tint(ForgeTheme.primary)
        #if os(iOS)
        .onAppear {
            // Style the tab bar to match the dark theme
            let tabBarAppearance = UITabBarAppearance()
            tabBarAppearance.configureWithOpaqueBackground()
            tabBarAppearance.backgroundColor = UIColor(ForgeTheme.dark900)
            UITabBar.appearance().standardAppearance = tabBarAppearance
            UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance

            // Style the navigation bar to match
            let navAppearance = UINavigationBarAppearance()
            navAppearance.configureWithOpaqueBackground()
            navAppearance.backgroundColor = UIColor(ForgeTheme.dark800)
            navAppearance.titleTextAttributes = [.foregroundColor: UIColor.white]
            navAppearance.largeTitleTextAttributes = [.foregroundColor: UIColor.white]
            UINavigationBar.appearance().standardAppearance = navAppearance
            UINavigationBar.appearance().scrollEdgeAppearance = navAppearance
            UINavigationBar.appearance().compactAppearance = navAppearance
        }
        #endif
        #if os(macOS)
        .frame(minWidth: 600, minHeight: 400)
        #endif
    }
}
