import SwiftUI

struct ForgeBackgroundLayer: View {
    @State private var animateParticles = false

    var body: some View {
        ZStack {
            ForgeTheme.shellGradient

            RadialGradient(
                colors: [ForgeTheme.primary.opacity(0.18), .clear],
                center: .init(x: 0.2, y: 0.8),
                startRadius: 20,
                endRadius: 420
            )

            RadialGradient(
                colors: [ForgeTheme.amber.opacity(0.10), .clear],
                center: .init(x: 0.8, y: 0.2),
                startRadius: 20,
                endRadius: 380
            )

            RadialGradient(
                colors: [ForgeTheme.primary.opacity(0.09), .clear],
                center: .init(x: 0.5, y: 0.5),
                startRadius: 20,
                endRadius: 500
            )

            StarFieldView()
                .opacity(0.35)

            ParticleLayer(animate: animateParticles)
        }
        .ignoresSafeArea()
        .onAppear {
            withAnimation(.easeInOut(duration: 8).repeatForever(autoreverses: true)) {
                animateParticles = true
            }
        }
    }
}

private struct StarFieldView: View {
    private let stars: [CGPoint] = [
        CGPoint(x: 0.05, y: 0.12), CGPoint(x: 0.10, y: 0.31), CGPoint(x: 0.18, y: 0.20),
        CGPoint(x: 0.24, y: 0.46), CGPoint(x: 0.32, y: 0.16), CGPoint(x: 0.41, y: 0.29),
        CGPoint(x: 0.53, y: 0.11), CGPoint(x: 0.62, y: 0.38), CGPoint(x: 0.70, y: 0.23),
        CGPoint(x: 0.79, y: 0.17), CGPoint(x: 0.86, y: 0.33), CGPoint(x: 0.94, y: 0.22),
        CGPoint(x: 0.12, y: 0.62), CGPoint(x: 0.22, y: 0.78), CGPoint(x: 0.37, y: 0.67),
        CGPoint(x: 0.48, y: 0.84), CGPoint(x: 0.61, y: 0.73), CGPoint(x: 0.74, y: 0.81),
        CGPoint(x: 0.88, y: 0.70)
    ]

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                ForEach(stars.indices, id: \.self) { index in
                    Circle()
                        .fill(Color.white.opacity(index.isMultiple(of: 3) ? 0.42 : 0.26))
                        .frame(width: index.isMultiple(of: 4) ? 2.2 : 1.6, height: index.isMultiple(of: 4) ? 2.2 : 1.6)
                        .position(
                            x: stars[index].x * proxy.size.width,
                            y: stars[index].y * proxy.size.height
                        )
                }
            }
        }
    }
}

private struct ParticleLayer: View {
    let animate: Bool

    private let anchors: [CGPoint] = [
        CGPoint(x: 0.10, y: 0.20), CGPoint(x: 0.20, y: 0.60), CGPoint(x: 0.30, y: 0.40),
        CGPoint(x: 0.50, y: 0.80), CGPoint(x: 0.70, y: 0.30), CGPoint(x: 0.80, y: 0.70),
        CGPoint(x: 0.90, y: 0.50), CGPoint(x: 0.15, y: 0.86)
    ]

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                ForEach(anchors.indices, id: \.self) { index in
                    Circle()
                        .fill((index.isMultiple(of: 2) ? ForgeTheme.primary : ForgeTheme.amber).opacity(0.55))
                        .frame(width: 4, height: 4)
                        .position(
                            x: anchors[index].x * proxy.size.width,
                            y: anchors[index].y * proxy.size.height + (animate ? -16 : 8)
                        )
                        .blur(radius: animate ? 0 : 0.2)
                }
            }
        }
        .animation(.easeInOut(duration: 7.5).repeatForever(autoreverses: true), value: animate)
    }
}
