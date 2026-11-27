import SwiftUI

struct JurisOrbView: View {
    @State private var pulse = false

    var body: some View {
        ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            Color(red: 84/255, green: 181/255, blue: 237/255).opacity(0.35),
                            Color(red: 40/255, green: 127/255, blue: 189/255).opacity(0.12),
                            .clear
                        ],
                        center: .center,
                        startRadius: 8,
                        endRadius: 100
                    )
                )
                .scaleEffect(pulse ? 1.08 : 0.94)
            Circle()
                .stroke(Color(red: 84/255, green: 181/255, blue: 237/255).opacity(0.55), lineWidth: 1)
                .padding(22)
            Circle()
                .stroke(Color(red: 40/255, green: 127/255, blue: 189/255).opacity(0.22), lineWidth: 1)
                .padding(10)
            Circle()
                .fill(
                    RadialGradient(
                        colors: [.white, Color(red: 189/255, green: 235/255, blue: 1), Color(red: 84/255, green: 181/255, blue: 237/255), Color(red: 40/255, green: 127/255, blue: 189/255)],
                        center: .init(x: 0.34, y: 0.30),
                        startRadius: 1,
                        endRadius: 70
                    )
                )
                .frame(width: 88, height: 88)
                .shadow(color: Color(red: 84/255, green: 181/255, blue: 237/255).opacity(0.45), radius: 24)
        }
        .accessibilityLabel("JURIS, assistant prêt")
        .onAppear {
            withAnimation(.easeInOut(duration: 3.8).repeatForever(autoreverses: true)) {
                pulse = true
            }
        }
        .accessibilityReduceMotion(pulse ? .reduce : .noPreference)
    }
}
