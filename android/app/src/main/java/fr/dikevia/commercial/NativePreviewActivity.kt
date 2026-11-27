package fr.dikevia.commercial

import android.os.Bundle
import android.widget.Toast
import androidx.fragment.app.FragmentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import fr.dikevia.commercial.core.api.DikeviaApiClient
import fr.dikevia.commercial.core.api.DikeviaOrganization
import fr.dikevia.commercial.core.auth.Auth0NativeAuth
import fr.dikevia.commercial.feature.home.NativeHomeScreen
import com.auth0.android.result.Credentials
import java.util.concurrent.Executors

/**
 * Native end-to-end preview: Auth0 -> organization membership -> existing chat API.
 * This activity remains isolated from the production launcher until Auth0 tenant
 * configuration and physical-device acceptance tests are complete.
 */
class NativePreviewActivity : FragmentActivity() {
    private lateinit var auth: Auth0NativeAuth
    private val api = DikeviaApiClient()
    private val io = Executors.newSingleThreadExecutor()

    private var credentials: Credentials? = null
    private var authenticated by mutableStateOf(false)
    private var organizations by mutableStateOf<List<DikeviaOrganization>>(emptyList())
    private var selectedOrganizationId by mutableStateOf<String?>(null)
    private var conversationId: String? = null
    private var chatAnswer by mutableStateOf("")
    private var chatStatus by mutableStateOf("")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        auth = Auth0NativeAuth(this, this)

        auth.restore(
            onSuccess = { restored ->
                runOnUiThread {
                    credentials = restored
                    authenticated = true
                    chatStatus = "Restauration de votre espace…"
                }
                loadOrganizations(restored)
            },
            onUnavailable = {
                runOnUiThread {
                    credentials = null
                    authenticated = false
                    organizations = emptyList()
                    selectedOrganizationId = null
                    chatStatus = ""
                }
            }
        )

        val administrationEdition = BuildConfig.FLAVOR == "admin"
        setContent {
            NativeHomeScreen(
                administrationEdition = administrationEdition,
                authenticated = authenticated,
                organizations = organizations,
                selectedOrganizationId = selectedOrganizationId,
                onSelectOrganization = { selectedOrganizationId = it },
                chatAnswer = chatAnswer,
                chatStatus = chatStatus,
                onSignIn = {
                    auth.login(
                        onSuccess = { signedIn ->
                            runOnUiThread {
                                credentials = signedIn
                                authenticated = true
                                chatAnswer = ""
                                conversationId = null
                                chatStatus = "Connexion réussie. Chargement de vos organisations…"
                            }
                            loadOrganizations(signedIn)
                        },
                        onError = { message ->
                            runOnUiThread {
                                chatStatus = message
                                Toast.makeText(this, message, Toast.LENGTH_LONG).show()
                            }
                        }
                    )
                },
                onSignOut = {
                    auth.logout(
                        onComplete = {
                            runOnUiThread {
                                credentials = null
                                authenticated = false
                                organizations = emptyList()
                                selectedOrganizationId = null
                                conversationId = null
                                chatAnswer = ""
                                chatStatus = ""
                                Toast.makeText(this, "Déconnexion effectuée.", Toast.LENGTH_SHORT).show()
                            }
                        },
                        onError = { message ->
                            runOnUiThread {
                                chatStatus = message
                                Toast.makeText(this, message, Toast.LENGTH_LONG).show()
                            }
                        }
                    )
                },
                onSendQuestion = ::sendQuestion
            )
        }
    }

    private fun loadOrganizations(session: Credentials) {
        io.execute {
            try {
                val result = api.organizations(session.accessToken, session.idToken)
                runOnUiThread {
                    organizations = result
                    selectedOrganizationId = result.singleOrNull()?.id
                        ?: selectedOrganizationId?.takeIf { id -> result.any { it.id == id } }
                    chatStatus = when {
                        result.isEmpty() -> "Aucune organisation active n'est rattachée à ce compte. Contactez l'administrateur."
                        result.size > 1 && selectedOrganizationId == null -> "Sélectionnez l'organisation à utiliser."
                        else -> "Espace sécurisé prêt."
                    }
                }
            } catch (error: Exception) {
                runOnUiThread {
                    organizations = emptyList()
                    selectedOrganizationId = null
                    chatStatus = error.message ?: "Impossible de charger vos organisations."
                }
            }
        }
    }

    private fun sendQuestion(question: String) {
        if (BuildConfig.FLAVOR == "admin") {
            chatStatus = "L'application Administration ne donne pas accès à JURIS."
            return
        }
        val session = credentials
        val organizationId = selectedOrganizationId
        if (session == null || organizationId == null) {
            chatStatus = "Authentifiez-vous et sélectionnez une organisation avant d'interroger JURIS."
            return
        }
        chatStatus = "JURIS analyse votre question et vérifie les sources…"
        chatAnswer = ""
        io.execute {
            try {
                val answer = api.ask(
                    session.accessToken,
                    session.idToken,
                    organizationId,
                    question,
                    conversationId
                )
                runOnUiThread {
                    conversationId = answer.conversationId
                    chatAnswer = buildString {
                        append(answer.answer)
                        answer.clarificationQuestion?.let {
                            append("\n\nPrécision nécessaire : ")
                            append(it)
                        }
                        if (answer.sources.isNotEmpty()) {
                            append("\n\nSources consultées : ")
                            append(answer.sources.joinToString(" ; "))
                        }
                    }
                    chatStatus = "Statut de vérification : ${answer.verificationStatus}"
                }
            } catch (error: Exception) {
                runOnUiThread {
                    chatStatus = error.message ?: "Le service JURIS est momentanément indisponible."
                }
            }
        }
    }

    override fun onDestroy() {
        io.shutdown()
        super.onDestroy()
    }
}
