package fr.dikevia.commercial

import android.os.Bundle
import android.widget.Toast
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.activity.result.contract.ActivityResultContracts
import androidx.fragment.app.FragmentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.setValue
import fr.dikevia.commercial.core.api.DikeviaApiClient
import fr.dikevia.commercial.core.api.DikeviaOrganization
import fr.dikevia.commercial.core.api.DikeviaInstanceSession
import fr.dikevia.commercial.core.auth.Auth0NativeAuth
import fr.dikevia.commercial.feature.home.NativeHomeScreen
import fr.dikevia.commercial.feature.home.JurisChatMessage
import fr.dikevia.commercial.feature.home.JurisChatAttachment
import com.auth0.android.result.Credentials
import java.util.concurrent.Executors
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Native end-to-end preview: Auth0 -> organization membership -> existing chat API.
 * This activity remains isolated from the production launcher until Auth0 tenant
 * configuration and physical-device acceptance tests are complete.
 */
class NativePreviewActivity : FragmentActivity() {
    private lateinit var auth: Auth0NativeAuth
    private val api = DikeviaApiClient()
    private val io = Executors.newSingleThreadExecutor()
    private var textToSpeech: TextToSpeech? = null
    private var speaking by mutableStateOf(false)
    private var pendingPdfText: String? = null
    private var pendingZipAttachments: List<JurisChatAttachment> = emptyList()
    private val createZip = registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        val files = pendingZipAttachments
        pendingZipAttachments = emptyList()
        if (uri != null && files.isNotEmpty()) {
            runCatching {
                contentResolver.openOutputStream(uri)?.use { stream ->
                    ZipOutputStream(stream).use { zip ->
                        val used = mutableSetOf<String>()
                        files.forEachIndexed { index, item ->
                            var name = item.fileName.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "document_$index" }
                            val base = name.substringBeforeLast('.', name)
                            val extension = name.substringAfterLast('.', "")
                            var suffix = 1
                            while (!used.add(name.lowercase(Locale.ROOT))) {
                                name = if (extension.isBlank()) "${base}_${suffix++}" else "${base}_${suffix++}.$extension"
                            }
                            zip.putNextEntry(ZipEntry(name))
                            zip.write(item.bytes)
                            zip.closeEntry()
                        }
                    }
                } ?: error("Impossible d'écrire l'archive ZIP.")
            }.onSuccess { Toast.makeText(this, "Archive ZIP créée.", Toast.LENGTH_SHORT).show() }
                .onFailure { Toast.makeText(this, it.message ?: "Échec de création du ZIP.", Toast.LENGTH_LONG).show() }
        }
    }
    private val createPdf = registerForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri ->
        val text = pendingPdfText
        pendingPdfText = null
        if (uri != null && text != null) {
            runCatching { contentResolver.openOutputStream(uri)?.use { it.write(buildAnswerPdf(text)) } ?: error("Impossible d'écrire le PDF.") }
                .onSuccess { Toast.makeText(this, "PDF JURIS enregistré.", Toast.LENGTH_SHORT).show() }
                .onFailure { Toast.makeText(this, it.message ?: "Échec de la création du PDF.", Toast.LENGTH_LONG).show() }
        }
    }

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
    private var savedSessions by mutableStateOf<List<DikeviaInstanceSession>>(emptyList())
    private var savingSession by mutableStateOf(false)
    private var preparingInstance by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        auth = Auth0NativeAuth(this, this)
        textToSpeech = TextToSpeech(this) { status -> if (status == TextToSpeech.SUCCESS) textToSpeech?.language = Locale.FRANCE }
        textToSpeech?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) { runOnUiThread { speaking = true } }
            override fun onDone(utteranceId: String?) { runOnUiThread { speaking = false } }
            @Deprecated("Deprecated by Android")
            override fun onError(utteranceId: String?) { runOnUiThread { speaking = false } }
        })

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
                    conversationEpoch += 1
                    chatTranscript.clear()
                },
                factsStartDate = factsStartDate,
                onFactsStartDateChange = {
                    if (factsStartDate != it) {
                        factsStartDate = it
                        resetConversationForContextChange()
                    }
                },
                factsEndDate = factsEndDate,
                onFactsEndDateChange = {
                    if (factsEndDate != it) {
                        factsEndDate = it
                        resetConversationForContextChange()
                    }
                },
                situationOngoing = situationOngoing,
                onSituationOngoingChange = {
                    if (situationOngoing != it) {
                        situationOngoing = it
                        if (it) factsEndDate = ""
                        resetConversationForContextChange()
                    }
                },
                confirmLocalDocumentAiTransfer = confirmLocalDocumentAiTransfer,
                onConfirmLocalDocumentAiTransferChange = { confirmLocalDocumentAiTransfer = it },
                onSelectOrganization = {
                    if (selectedOrganizationId != it) {
                        selectedOrganizationId = it
                        savedSessions = emptyList()
                        refreshInstanceSessions(it)
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
                savedSessions = savedSessions,
                savingSession = savingSession,
                onSaveSession = ::saveInstanceSession,
                onRefreshSessions = { selectedOrganizationId?.let { refreshInstanceSessions(it) } },
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
                                savedSessions = emptyList()
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
                onSendQuestion = ::sendQuestion,
                onReadAloud = ::readAloud,
                onStopReading = { textToSpeech?.stop(); speaking = false },
                isSpeaking = speaking,
                onExportPdf = ::exportAnswerPdf,
                onCreateZip = ::createAttachmentZip
            )
        }
    }

    private fun resetConversationForContextChange() {
        conversationId = null
        conversationEpoch += 1
        chatTranscript.clear()
    }

    private fun loadOrganizations(session: Credentials) {
        io.execute {
            try {
                val result = api.organizations(session.accessToken, session.idToken)
                runOnUiThread {
                    organizations = result
                    selectedOrganizationId = result.singleOrNull()?.id
                        ?: selectedOrganizationId?.takeIf { id -> result.any { it.id == id } }
                    selectedOrganizationId?.let { refreshInstanceSessions(it, session) }
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


    private fun refreshInstanceSessions(organizationId: String, restored: Credentials? = credentials) {
        val session = restored ?: return
        io.execute {
            try {
                val result = api.listInstanceSessions(session.accessToken, session.idToken, organizationId)
                runOnUiThread {
                    if (selectedOrganizationId == organizationId) savedSessions = result
                }
            } catch (error: Exception) {
                runOnUiThread {
                    if (selectedOrganizationId == organizationId) {
                        chatStatus = error.message ?: "Impossible de charger les dossiers de séance."
                    }
                }
            }
        }
    }

    private fun saveInstanceSession(instance: String, title: String, meetingDate: String, minutes: String) {
        if (BuildConfig.FLAVOR == "admin") return
        val session = credentials
        val organizationId = selectedOrganizationId
        if (session == null || organizationId == null) {
            chatStatus = "Authentifiez-vous et sélectionnez une organisation avant d'enregistrer une séance."
            return
        }
        val preparation = runCatching { org.json.JSONObject(instancePreparation) }.getOrElse { org.json.JSONObject() }
        savingSession = true
        chatStatus = "Enregistrement du dossier de séance…"
        io.execute {
            try {
                val created = api.createInstanceSession(
                    session.accessToken, session.idToken, organizationId,
                    instance, title, meetingDate.ifBlank { null }, preparation, minutes
                )
                runOnUiThread {
                    savingSession = false
                    if (selectedOrganizationId == organizationId) {
                        savedSessions = listOf(created) + savedSessions.filterNot { it.id == created.id }
                        chatStatus = "Séance enregistrée. Tu peux la retrouver dans tes dossiers."
                    }
                }
            } catch (error: Exception) {
                runOnUiThread {
                    savingSession = false
                    chatStatus = error.message ?: "L'enregistrement de la séance a échoué."
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

    private fun sendQuestion(question: String, attachments: List<JurisChatAttachment>) {
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
        if (attachments.isNotEmpty() && !allowLocalAiTransfer) {
            chatStatus = "Pour analyser ces pièces, confirmez d'abord leur transfert au service IA dans le champ de consentement."
            return
        }
        confirmLocalDocumentAiTransfer = false
        if (session == null || organizationId == null) {
            chatStatus = "Authentifiez-vous et sélectionnez une organisation avant d'interroger JURIS."
            return
        }
        chatTranscript.add(JurisChatMessage("user", buildString {
            append(question.trim())
            if (attachments.isNotEmpty()) append("\n\nPièces jointes : ").append(attachments.joinToString(", ") { it.fileName })
        }))
        chatStatus = if (attachments.isEmpty()) "JURIS analyse votre question et vérifie les sources…" else "JURIS prépare la lecture de vos pièces jointes…"
        sending = true
        io.execute {
            try {
                var enrichedQuestion = question.trim()
                if (attachments.isNotEmpty()) {
                    val extracted = attachments.map { attachment ->
                        api.uploadChatAttachment(
                            session.accessToken,
                            session.idToken,
                            attachment.fileName,
                            attachment.mimeType,
                            attachment.bytes
                        )
                    }.joinToString("\n\n").take(60_000)
                    enrichedQuestion += "\n\nPIÈCES JOINTES TRANSMISES ET TEXTE EXTRAIT :\n$extracted\n\nAnalyse ces pièces dans le cadre de ma question. Distingue les éléments lisibles des éléments non extraits. N'invente pas le contenu des fichiers."
                }
                runOnUiThread { chatStatus = "JURIS analyse votre demande et vérifie les sources…" }
                val answer = api.ask(
                    session.accessToken,
                    session.idToken,
                    organizationId,
                    enrichedQuestion,
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

    private fun readAloud(text: String) {
        val engine = textToSpeech
        if (engine == null) {
            Toast.makeText(this, "La synthèse vocale n'est pas encore prête.", Toast.LENGTH_SHORT).show()
            return
        }
        val result = engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "juris-answer")
        if (result == TextToSpeech.ERROR) {
            Toast.makeText(this, "La lecture vocale n'a pas pu démarrer.", Toast.LENGTH_SHORT).show()
        } else speaking = true
    }

    private fun createAttachmentZip(attachments: List<JurisChatAttachment>) {
        if (attachments.isEmpty()) return
        pendingZipAttachments = attachments
        createZip.launch("JURIS-pieces-jointes.zip")
    }

    private fun exportAnswerPdf(text: String) {
        pendingPdfText = text
        createPdf.launch("JURIS-reponse.pdf")
    }

    private fun buildAnswerPdf(text: String): ByteArray {
        val document = PdfDocument()
        val pageWidth = 595
        val pageHeight = 842
        val margin = 48f
        val bodyPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.rgb(23, 40, 59)
            textSize = 11f
            typeface = Typeface.create("sans-serif", Typeface.NORMAL)
        }
        val titlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.rgb(23, 40, 59)
            textSize = 22f
            typeface = Typeface.create("sans-serif", Typeface.BOLD)
        }
        val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.rgb(40, 127, 189)
            textSize = 9f
            typeface = Typeface.create("sans-serif", Typeface.BOLD)
        }
        val maxWidth = pageWidth - margin * 2
        val lines = mutableListOf<String>()
        text.replace("\\r", "").split("\\n").forEach { paragraph ->
            if (paragraph.isBlank()) lines.add("")
            else {
                var current = ""
                paragraph.split(Regex("\\s+")).forEach { word ->
                    val candidate = if (current.isEmpty()) word else "$current $word"
                    if (bodyPaint.measureText(candidate) <= maxWidth) current = candidate
                    else {
                        if (current.isNotEmpty()) lines.add(current)
                        current = word
                    }
                }
                if (current.isNotEmpty()) lines.add(current)
            }
        }
        var pageNumber = 1
        var page = document.startPage(PdfDocument.PageInfo.Builder(pageWidth, pageHeight, pageNumber).create())
        var y = 64f
        page.canvas.drawText("JURIS", margin, y, titlePaint)
        y += 22f
        val date = java.text.SimpleDateFormat("dd/MM/yyyy", Locale.FRANCE).format(java.util.Date())
        page.canvas.drawText("Réponse de votre assistant juridique — $date", margin, y, labelPaint)
        y += 30f
        lines.forEach { line ->
            if (y > pageHeight - 55f) {
                page.canvas.drawText("Dikévia · JURIS", margin, pageHeight - 28f, labelPaint)
                document.finishPage(page)
                pageNumber += 1
                page = document.startPage(PdfDocument.PageInfo.Builder(pageWidth, pageHeight, pageNumber).create())
                y = 58f
            }
            if (line.isNotEmpty()) page.canvas.drawText(line, margin, y, bodyPaint)
            y += 17f
        }
        page.canvas.drawText("Dikévia · JURIS", margin, pageHeight - 28f, labelPaint)
        document.finishPage(page)
        val output = java.io.ByteArrayOutputStream()
        document.writeTo(output)
        document.close()
        return output.toByteArray()
    }

    override fun onDestroy() {
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        io.shutdown()
        super.onDestroy()
    }
}
