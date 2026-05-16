// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "ForgeInboxLite",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "ForgeInboxLite", targets: ["ForgeInboxLite"])
    ],
    targets: [
        .executableTarget(
            name: "ForgeInboxLite",
            path: "Sources/ForgeInboxLite"
        )
    ]
)
