import SwiftUI

private enum DikeviaPalette {
    static let background = Color(red: 0.953, green: 0.969, blue: 0.984)
    static let navy = Color(red: 0.090, green: 0.157, blue: 0.231)
    static let blue = Color(red: 0.157, green: 0.498, blue: 0.741)
    static let border = Color(red: 0.863, green: 0.902, blue: 0.941)
}

struct ContentView: View {
    @State private var question = ""
    // Authentication and API wiring are deliberately injected in a later,
    // separately validated step. Never display fabricated legal responses.
    private let isAuthenticated = false
    private let isAdministrationEdition = false

    private let instances: [(String, String, String)] = [
        ("CST", "Comité social territorial", "Organisation et conditions de travail"),
        ("CAP", "Commission administrative paritaire", "Carrière et situations individuelles"),
        ("CCP", "Commission consultative paritaire", "Agents contractuels"),
        ("F3SCT", "Formation spécialisée", "Santé, sécurité et conditions de travail")
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 22) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("DIKÉVIA")
                                .font(.caption.weight(.bold))
                                .tracking(2)
                                .foregroundStyle(DikeviaPalette.navy)
                            Text(isAdministrationEdition ? "Administration" : "L’assistance juridique des agents")
                                .font(.headline.weight(.semibold))
                                .foregroundStyle(DikeviaPalette.navy)
                        }
                        Spacer()
                        Button("Se connecter") {
                            // Auth0 native authorization is wired only after a
                            // dedicated Native application is configured.
                        }
                        .font(.subheadline.weight(.semibold))
                        .disabled(isAuthenticated)
                    }

                    if isAdministrationEdition {
                        adminContent
                    } else {
                        JurisOrbView()
                            .frame(width: 150, height: 150)
                            .padding(.top, 8)
                        VStack(spacing: 5) {
                            Text("JURIS")
                                .font(.system(size: 27, weight: .bold, design: .rounded))
                                .tracking(3)
                                .foregroundStyle(DikeviaPalette.navy)
                            Text("Votre assistant juridique territorial")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }

                        VStack(alignment: .leading, spacing: 12) {
                            Text("Préparer vos instances")
                                .font(.headline)
                                .foregroundStyle(DikeviaPalette.navy)
                            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                                ForEach(instances, id: \.0) { item in
                                    VStack(alignment: .leading, spacing: 7) {
                                        Text(item.0)
                                            .font(.title3.bold())
                                            .foregroundStyle(DikeviaPalette.blue)
                                        Text(item.1)
                                            .font(.subheadline.weight(.semibold))
                                            .foregroundStyle(DikeviaPalette.navy)
                                        Text(item.2)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    .frame(maxWidth: .infinity, minHeight: 112, alignment: .leading)
                                    .padding(13)
                                    .background(.white, in: RoundedRectangle(cornerRadius: 16))
                                    .overlay(RoundedRectangle(cornerRadius: 16).stroke(DikeviaPalette.border))
                                }
                            }
                        }

                        VStack(spacing: 10) {
                            TextField(
                                isAuthenticated ? "Posez votre question à JURIS…" : "Connectez-vous pour interroger JURIS",
                                text: $question,
                                axis: .vertical
                            )
                            .lineLimit(2...4)
                            .padding(13)
                            .background(.white, in: RoundedRectangle(cornerRadius: 14))
                            .overlay(RoundedRectangle(cornerRadius: 14).stroke(DikeviaPalette.border))
                            .disabled(!isAuthenticated)
                            Button("Envoyer à JURIS") {
                                // Connected to the authenticated API client in the next integration step.
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 13)
                            .background(DikeviaPalette.blue, in: RoundedRectangle(cornerRadius: 13))
                            .foregroundStyle(.white)
                            .disabled(!isAuthenticated || question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        }
                        Text("La connexion sécurisée est nécessaire pour accéder à vos espaces et à vos données.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(20)
            }
            .background(DikeviaPalette.background.ignoresSafeArea())
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    private var adminContent: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Pilotage de Dikévia")
                .font(.title2.bold())
                .foregroundStyle(DikeviaPalette.navy)
            Text("Gestion des utilisateurs, collectivités, droits et abonnements.")
                .foregroundStyle(.secondary)
            ForEach([
                ("Utilisateurs et accès", "Comptes, invitations et rôles"),
                ("Collectivités", "Organisations et rattachements"),
                ("Abonnements", "Offres, droits et facturation"),
                ("Supervision", "Disponibilité et activité du service")
            ], id: \.0) { item in
                VStack(alignment: .leading, spacing: 5) {
                    Text(item.0).font(.headline).foregroundStyle(DikeviaPalette.navy)
                    Text(item.1).font(.caption).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(16)
                .background(.white, in: RoundedRectangle(cornerRadius: 15))
                .overlay(RoundedRectangle(cornerRadius: 15).stroke(DikeviaPalette.border))
            }
            Text("L’administration ne donne pas accès au chatbot juridique des agents.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
