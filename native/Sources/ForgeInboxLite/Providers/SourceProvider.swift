import SwiftUI

protocol SourceProvider {
    var type: SourceType { get }
    var displayName: String { get }

    func makeMainView(for source: Source, onProviderConfigUpdate: ((Data?) -> Void)?) -> AnyView
}
