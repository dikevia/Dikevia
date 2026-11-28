package fr.dikevia.commercial

import android.os.Bundle
import android.widget.Toast
import androidx.fragment.app.FragmentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.setValue
import fr.dikevia.commercial.core.api.DikeviaApiClient
import fr.dikevia.commercial.core.api.DikeviaOrganization
import fr.dikevia.commercial.core.auth.Auth0NativeAuth
import fr.dikevia.commercial.feature.home.NativeHomeScreen
import fr.dikevia.commercial.feature.home.JurisChatMessage
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
    private var publicService by mutableStateOf("FPT")
    private var employer by mutableStateOf("NATIONAL")
    private var employerDetails by mutableStateOf("")
    private var factsStartDate by mutableStateOf("")
    private var factsEndDate by mutableStateOf("")
    private var situationOngoing by mutableStateOf(false)
    private var confirmLocalDocumentAiTransfer by mutableStateOf(false)
    private var conversationId: String? = null
    private var conversationEpoch: Long = 0L
    private val chatTranscript = mutableStateListOf<JurisChatMessage>()
    private var chatStatus by mutableStateOf("")
    private var sending by mutableStateOf(false)
    private var instancePreparation by mutableStateOf("")
    private var preparingInstance by mutableStateOf(false)

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
                publicService = publicService,
                onPublicServiceChange = {
                    if (publicService != it) {
                        publicService = it
                        employer = "NATIONAL"
                        employerDetails = ""
                        conversationId = null
                        conversationEpoch += 1
                        chatTranscript.clear()
                        chatStatus = "Versant modifié. Une nouvelle conversation sera ouverte."
                    }
                },
                employer = employer,
                onEmployerChange = {
                    if (employer != it) {
                        employer = it
                        conversationId = null
                        conversationEpoch += 1
                        chatTranscript.clear()
                    }
                },
                employerDetails = employerDetails,
                onEmployerDetailsChange = {
                    employerDetails = it
                    conversationId = null
                    chatTranscript.clear()
                },
                factsStartDate = factsStartDate,
                onFactsStartDateChange = { factsStartDate = it },
                factsEndDate = factsEndDate,
                onFactsEndDateChange = { factsEndDate = it },
                situationOngoing = situationOngoing,
                onSituationOngoingChange = {
                    situationOngoing = it
                    if (it) factsEndDate = ""
                },
                confirmLocalDocumentAiTransfer = confirmLocalDocumentAiTransfer,
                onConfirmLocalDocumentAiTransferChange = { confirmLocalDocumentAiTransfer = it },
                onSelectOrganization = {
                    if (selectedOrganizationId != it) {
                        selectedOrganizationId = it
                        conversationId = null
                        conversationEpoch += 1
                        chatTranscript.clear()
                        chatStatus = "Organisation changée. Une nouvelle conversation sera ouverte."
                    }
                },
                chatTranscript = chatTranscript.toList(),
                chatStatus = chatStatus,
                sending = sending,
                instancePreparation = instancePreparation,
                preparingInstance = preparingInstance,
                onPrepareInstance = ::prepareInstance,
                onSignIn = {
                    auth.login(
                        onSuccess = { signedIn ->
                            runOnUiThread {
                                credentials = signedIn
                                authenticated = true
                                chatTranscript.clear()
                                conversationId = null
                                conversationEpoch += 1
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
                                conversationEpoch += 1
                                chatTranscript.clear()
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

    private fun prepareInstance(instance: String, objet: String) {
        if (BuildConfig.FLAVOR == "admin") return
        val session = credentials
        val organizationId = selectedOrganizationId
        if (session == null || organizationId == null) {
            chatStatus = "Authentifiez-vous et sélectionnez une organisation avant de préparer une instance."
            return
        }
        preparingInstance = true
        instancePreparation = ""
        chatStatus = "Préparation de l'ordre du jour $instance et recherche des sources juridiques…"
        io.execute {
            try {
                // The backend's canonical instance key is FS; keep the public F3SCT label in the Android UI.
                val backendInstance = if (instance.equals("F3SCT", ignoreCase = true)) "FS" else instance
                val result = api.prepareInstance(
                    session.accessToken,
                    session.idToken,
                    organizationId,
                    backendInstance,
                    objet
                )
                runOnUiThread {
                    preparingInstance = false
                    if (selectedOrganizationId != organizationId) return@runOnUiThread
                    instancePreparation = result
                    chatStatus = "Préparation terminée. Les pistes et sources doivent être vérifiées avant la séance."
                }
            } catch (error: Exception) {
                runOnUiThread {
                    preparingInstance = false
                    chatStatus = error.message ?: "La préparation de l'instance a échoué."
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
        val selectedVersant = publicService
        val selectedEmployer = if (selectedVersant == "FPT") employer else employerDetails.trim().ifBlank { "NATIONAL" }
        val startDate = factsStartDate.trim().ifBlank { null }
        val endDate = factsEndDate.trim().ifBlank { null }
        val ongoing = situationOngoing
        val allowLocalAiTransfer = confirmLocalDocumentAiTransfer
        val conversationAtSend = conversationId
        val conversationEpochAtSend = conversationEpoch
        confirmLocalDocumentAiTransfer = false
        if (session == null || organizationId == null) {
            chatStatus = "Authentifiez-vous et sélectionnez une organisation avant d'interroger JURIS."
            return
        }
        chatTranscript.add(JurisChatMessage("user", question.trim()))
        chatStatus = "JURIS analyse votre question et vérifie les sources…"
        sending = true
        io.execute {
            try {
                val answer = api.ask(
                    session.accessToken,
                    session.idToken,
                    organizationId,
                    question,
                    selectedVersant,
                    selectedEmployer,
                    startDate,
                    endDate,
                    ongoing,
                    allowLocalAiTransfer,
                    conversationAtSend
                )
                runOnUiThread {
                    sending = false
                    if (selectedOrganizationId != organizationId || publicService != selectedVersant || conversationEpoch != conversationEpochAtSend) return@runOnUiThread
                    conversationId = answer.conversationId
                    val renderedAnswer = buildString {
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
                    chatTranscript.add(JurisChatMessage("assistant", renderedAnswer))
                    chatStatus = "Statut de vérification : ${answer.verificationStatus}"
                }
            } catch (error: Exception) {
                runOnUiThread {
                    sending = false
                    if (selectedOrganizationId == organizationId && publicService == selectedVersant && conversationEpoch == conversationEpochAtSend) {
                        val message = error.message ?: "Le service JURIS est momentanément indisponible."
                        chatTranscript.add(JurisChatMessage("assistant", "La demande n'a pas pu être traitée : $message"))
                        chatStatus = message
                    }
                }
            }
        }
    }

    override fun onDestroy() {
        io.shutdown()
        super.onDestroy()
    }
}
