import Foundation

enum SignalLaunchResult {
    case launched
    case signalNotInstalled
    case failed(Error)
}

struct SignalLauncher {
    private static let signalBinaryPath = "/Applications/Signal.app/Contents/MacOS/Signal"

    static func launch(account: Account) -> SignalLaunchResult {
        guard FileManager.default.fileExists(atPath: signalBinaryPath) else {
            return .signalNotInstalled
        }

        do {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: signalBinaryPath)
            process.arguments = ["--user-data-dir=\(account.profilePath)"]
            try process.run()
            return .launched
        } catch {
            return .failed(error)
        }
    }
}
