package fr.dikevia.commercial.feature.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.rememberDrawerState
import kotlinx.coroutines.launch
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import fr.dikevia.commercial.designsystem.JurisOrb
import fr.dikevia.commercial.designsystem.JurisOrbState
import fr.dikevia.commercial.core.api.DikeviaOrganization
import fr.dikevia.commercial.core.api.DikeviaInstanceSession
import org.json.JSONObject
import org.json.JSONArray

private val Glacier = Color(0xFFF3F7FB)
private val Navy = Color(0xFF17283B)
private val SteelBlue = Color(0xFF287FBD)
private val Border = Color(0xFFDCE6F0)

private data class InstanceCard(val acronym: String, val title: String, val description: String)

data class JurisChatMessage(val role: String, val content: String)

/**
 * Transfers the structured instance preparation into the existing JURIS chat.
 * This is a prompt hand-off, not a second assistant or a separate chat endpoint.
 */
private fun preparationMatchesInstance(rawPreparation: String, selectedInstance: String?): Boolean {
    if (selectedInstance.isNullOrBlank()) return false
    val prepared = runCatching { JSONObject(rawPreparation).optString("instance") }.getOrNull()
    val expected = if (selectedInstance.equals("F3SCT", ignoreCase = true)) "FS" else selectedInstance
    return prepared.equals(expected, ignoreCase = true)
}

private fun preparationLabel(key: String): String = when (key) {
    "instance" -> "Instance"
    "objet" -> "Objet examiné"
    "points" -> "Points de préparation"
    "code" -> "Thème"
    "libelle" -> "Sujet"
    "questions" -> "Questions à poser"
    "documents" -> "Documents à demander"
    "documents_a_demander" -> "Documents à réunir"
    "qualification" -> "Niveau de qualification"
    "qualification_a_completer" -> "Qualification à compléter"
    "notice" -> "Précautions"
    "legal_research" -> "Recherche juridique"
    "provider" -> "Source de recherche"
    "status" -> "État de la recherche"
    "requested_date" -> "Date de référence"
    "sources" -> "Sources identifiées"
    "searches" -> "Recherches effectuées"
    "family" -> "Famille juridique"
    "title" -> "Intitulé"
    "article" -> "Article"
    "official_number" -> "Référence officielle"
    "decision_date" -> "Date de décision"
    "case_number" -> "Numéro de décision"
    "excerpt" -> "Extrait"
    "official_url" -> "Lien officiel"
    "full_text_retrieved" -> "Texte intégral récupéré"
    "verification_note" -> "Note de vérification"
    "version_status" -> "État de la version"
    "valid_from" -> "En vigueur depuis"
    "valid_to" -> "En vigueur jusqu'au"
    "legal_conclusion" -> "Conclusion juridique établie"
    "result_count" -> "Nombre de résultats"
    "cst_qualification" -> "Compétence du CST"
    "fs_qualification" -> "Compétence de la formation spécialisée"
    "fs_operational_qualification" -> "Analyse opérationnelle de la formation spécialisée"
    "cst_fs_competence_routing" -> "Répartition des compétences CST / formation spécialisée"
    "cst_agenda_request" -> "Point inscrit à l'ordre du jour"
    "instance_meeting_deadlines" -> "Délais de réunion"
    "annual_meeting_frequency" -> "Fréquence annuelle"
    "fs_agenda_preparation" -> "Préparation de l'ordre du jour"
    "qualification" -> "Qualification"
    "status" -> "Statut"
    "notice" -> "Information"
    else -> key.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

@Composable
private fun SessionItemsSection(title: String, items: List<String>) {
    if (items.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, color = SteelBlue, fontWeight = FontWeight.SemiBold)
        items.forEachIndexed { index, raw ->
            val display = remember(raw) {
                runCatching {
                    val item = JSONObject(raw)
                    listOf("title", "name", "description", "question", "document", "assignee", "due_date", "status")
                        .mapNotNull { key -> item.optString(key).takeIf { it.isNotBlank() && it != "null" } }
                        .distinct()
                        .joinToString(" — ")
                        .ifBlank { item.toString() }
                }.getOrElse { raw }
            }
            Text("• $display", color = Navy, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun InstancePreparationContent(raw: String) {
    val data = remember(raw) { runCatching { JSONObject(raw) }.getOrNull() }
    if (data == null) {
        Text("Le résultat de préparation n'a pas pu être interprété. Relancez la préparation ou contactez le support.", color = Navy)
        return
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        val instance = data.optString("instance")
        val objectText = data.optString("objet")
        if (instance.isNotBlank()) Text(if (instance == "FS") "Formation spécialisée (F3SCT)" else instance, color = SteelBlue, fontWeight = FontWeight.Bold)
        if (objectText.isNotBlank()) Text(objectText, color = Navy, fontWeight = FontWeight.SemiBold)
        val points = data.optJSONArray("points")
        if (points != null) {
            for (i in 0 until points.length()) {
                val point = points.optJSONObject(i) ?: continue
                Card(colors = CardDefaults.cardColors(containerColor = Glacier), shape = RoundedCornerShape(12.dp)) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                        Text(point.optString("libelle", "Point à examiner"), color = Navy, fontWeight = FontWeight.SemiBold)
                        val questions = point.optJSONArray("questions")
                        if (questions != null && questions.length() > 0) {
                            Text("Questions à poser", color = SteelBlue, fontWeight = FontWeight.SemiBold)
                            for (j in 0 until questions.length()) {
                                Text("• " + questions.optString(j), color = Navy, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        val documents = point.optJSONArray("documents")
                        if (documents != null && documents.length() > 0) {
                            Text("Documents à demander", color = SteelBlue, fontWeight = FontWeight.SemiBold)
                            for (j in 0 until documents.length()) {
                                Text("• " + documents.optString(j), color = Navy, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        val qualification = point.optString("qualification")
                        if (qualification.isNotBlank()) Text("Statut : piste à confirmer", color = Color(0xFF8A5A16), style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }
        val documents = data.optJSONArray("documents_a_demander")
        if (documents != null && documents.length() > 0) {
            Text("Liste récapitulative des documents", color = Navy, fontWeight = FontWeight.SemiBold)
            for (i in 0 until documents.length()) Text("• " + documents.optString(i), color = Navy, style = MaterialTheme.typography.bodySmall)
        }
        val research = data.optJSONObject("legal_research")
        if (research != null) {
            Card(colors = CardDefaults.cardColors(containerColor = Color.White), border = androidx.compose.foundation.BorderStroke(1.dp, Border), shape = RoundedCornerShape(12.dp)) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Recherche juridique", color = Navy, fontWeight = FontWeight.SemiBold)
                    val status = research.optString("status", "NON PRÉCISÉ")
                    Text("État : " + when (status) {
                        "NOT_CONFIGURED" -> "Recherche en direct non configurée"
                        "SEARCHED" -> "Recherche effectuée"
                        "PARTIAL" -> "Recherche partielle"
                        "NO_RESULT" -> "Aucun résultat trouvé"
                        "UNAVAILABLE" -> "Service de recherche indisponible"
                        else -> status
                    }, color = if (status == "SEARCHED") SteelBlue else Color(0xFF8A5A16), style = MaterialTheme.typography.bodySmall)
                    val date = research.optString("requested_date")
                    if (date.isNotBlank()) Text("Date de référence : $date", color = Navy, style = MaterialTheme.typography.bodySmall)
                    val sources = research.optJSONArray("sources")
                    if (sources != null && sources.length() > 0) {
                        Text("Sources identifiées", color = SteelBlue, fontWeight = FontWeight.SemiBold)
                        for (i in 0 until sources.length()) {
                            val source = sources.optJSONObject(i) ?: continue
                            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text(source.optString("title", "Source sans titre"), color = Navy, fontWeight = FontWeight.Medium)
                                val article = source.optString("article")
                                if (article.isNotBlank()) Text(article, color = Navy, style = MaterialTheme.typography.bodySmall)
                                val note = source.optString("verification_note")
                                if (note.isNotBlank()) Text(note, color = Color(0xFF62768A), style = MaterialTheme.typography.bodySmall)
                                val excerpt = source.optString("excerpt")
                                if (excerpt.isNotBlank()) Text(excerpt.take(700), color = Navy, style = MaterialTheme.typography.bodySmall)
                                val url = source.optString("official_url")
                                if (url.isNotBlank()) Text(url, color = SteelBlue, style = MaterialTheme.typography.bodySmall)
                            }
                            if (i < sources.length() - 1) Spacer(Modifier.height(6.dp))
                        }
                    } else {
                        Text("Aucune source juridique n'a été retournée. La fiche de préparation ne constitue pas une recherche juridique.", color = Color(0xFF8A5A16), style = MaterialTheme.typography.bodySmall)
                    }
                    val notice = research.optString("notice")
                    if (notice.isNotBlank()) Text(notice, color = Color(0xFF62768A), style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        val notice = data.optString("notice")
        if (notice.isNotBlank()) Text(notice, color = Color(0xFF62768A), style = MaterialTheme.typography.bodySmall)
        listOf("cst_qualification", "fs_qualification", "fs_operational_qualification").forEach { key ->
            val qualification = data.optJSONObject(key) ?: return@forEach
            Card(colors = CardDefaults.cardColors(containerColor = Color.White), border = androidx.compose.foundation.BorderStroke(1.dp, Border), shape = RoundedCornerShape(12.dp)) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text(preparationLabel(key), color = Navy, fontWeight = FontWeight.SemiBold)
                    val status = qualification.optString("status")
                    if (status.isNotBlank()) Text("État : $status", color = SteelBlue, style = MaterialTheme.typography.bodySmall)
                    val conclusion = qualification.optString("conclusion")
                    if (conclusion.isNotBlank()) Text(conclusion, color = Navy, style = MaterialTheme.typography.bodySmall)
                    val reasons = qualification.optJSONArray("reasons") ?: qualification.optJSONArray("questions")
                    if (reasons != null) for (i in 0 until reasons.length()) Text("• " + reasons.optString(i), color = Navy, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

private fun buildJurisInstancePrompt(rawPreparation: String): String {
    val data = runCatching { JSONObject(rawPreparation) }.getOrNull()
        ?: return "Je souhaite approfondir avec JURIS la préparation de l'instance suivante : $rawPreparation"

    val points = data.optJSONArray("points")
    val pointText = buildString {
        if (points != null) {
            for (index in 0 until minOf(points.length(), 8)) {
                val point = points.optJSONObject(index) ?: continue
                append("- ").append(point.optString("libelle")).append("\n")
                append("  Questions : ")
                val questions = point.optJSONArray("questions")
                if (questions != null) {
                    append((0 until minOf(questions.length(), 5)).joinToString(" ; ") { questions.optString(it) })
                }
                append("\n  Documents : ")
                val documents = point.optJSONArray("documents")
                if (documents != null) {
                    append((0 until minOf(documents.length(), 5)).joinToString(" ; ") { documents.optString(it) })
                }
                append("\n")
            }
        }
    }

    val research = data.optJSONObject("legal_research")
    val sources = research?.optJSONArray("sources")
    val sourceText = buildString {
        if (sources != null) {
            for (index in 0 until minOf(sources.length(), 8)) {
                val source = sources.optJSONObject(index) ?: continue
                append("- ").append(source.optString("title", "Source sans titre"))
                val article = source.optString("article")
                val number = source.optString("official_number")
                val date = source.optString("decision_date")
                if (article.isNotBlank()) append(" — ").append(article)
                if (number.isNotBlank()) append(" — ").append(number)
                if (date.isNotBlank()) append(" — décision du ").append(date)
                append(" — texte intégral récupéré : ").append(source.optBoolean("full_text_retrieved"))
                val url = source.optString("official_url")
                if (url.isNotBlank()) append(" — ").append(url)
                val excerpt = source.optString("excerpt")
                if (excerpt.isNotBlank()) append("\n  Extrait : ").append(excerpt.take(500))
                append("\n")
            }
        }
    }
    val qualifications = listOf(
        "cst_qualification",
        "fs_qualification",
        "fs_operational_qualification",
        "cst_fs_competence_routing",
        "cst_agenda_request",
        "instance_meeting_deadlines",
        "annual_meeting_frequency",
        "fs_agenda_preparation"
    ).mapNotNull { key ->
        data.optJSONObject(key)?.let { "$key : ${it.toString().take(700)}" }
    }.joinToString("\n")

    val context = buildString {
        append("Je souhaite approfondir la préparation de mon instance avec JURIS, dans cette conversation.\n\n")
        append("INSTANCE : ").append(if (data.optString("instance") == "FS") "F3SCT (FS)" else data.optString("instance")).append("\n")
        append("OBJET : ").append(data.optString("objet")).append("\n\n")
        append("PISTES DE PRÉPARATION :\n").append(pointText.ifBlank { "Aucune règle de checklist déclenchée ; analyser le sujet à partir des faits et des sources." })
        val notice = data.optString("notice")
        if (notice.isNotBlank()) append("\nNOTICE : ").append(notice.take(500))
        if (qualifications.isNotBlank()) append("\n\nQUALIFICATIONS ET CONTRÔLES DÉCLARATIFS :\n").append(qualifications)
        if (research != null) {
            append("\n\nRECHERCHE JURIDIQUE : ").append(research.optString("status", "non précisée"))
            append(" ; date de référence : ").append(research.optString("requested_date", "non précisée"))
        }
        if (sourceText.isNotBlank()) append("\nSOURCES RETOURNÉES :\n").append(sourceText)
    }
    val mission = "MISSION JURIS : approfondis cette préparation. Vérifie la compétence de l'instance, les textes et leur version applicable à la date des faits, ainsi que la jurisprudence pertinente. Distingue les faits déclarés des faits établis, les sources intégralement récupérées des simples métadonnées et les hypothèses des conclusions. Identifie les informations manquantes, pose les questions de clarification nécessaires, prépare des questions argumentées pour la séance et un plan d'action syndical. N'invente aucune source et ne conclus pas sans éléments suffisants."
    return (context.take(3800) + "\n\n" + mission).take(5000)
}


private val instances = listOf(
    InstanceCard("CST", "Comité social territorial", "Organisation et conditions de travail"),
    InstanceCard("CAP", "Commission administrative paritaire", "Carrière et situations individuelles"),
    InstanceCard("CCP", "Commission consultative paritaire", "Agents contractuels"),
    InstanceCard("F3SCT", "Formation spécialisée", "Santé, sécurité et conditions de travail")
)

/**
 * Native standard/admin home. Authentication and API actions are injected by the
 * application host; this view never fabricates a login or a legal answer.
 */
@Composable
fun NativeHomeScreen(
    administrationEdition: Boolean,
    authenticated: Boolean,
    onSignIn: () -> Unit,
    onSignOut: () -> Unit,
    organizations: List<DikeviaOrganization>,
    selectedOrganizationId: String?,
    publicService: String,
    onPublicServiceChange: (String) -> Unit,
    employer: String,
    onEmployerChange: (String) -> Unit,
    employerDetails: String,
    onEmployerDetailsChange: (String) -> Unit,
    factsStartDate: String,
    onFactsStartDateChange: (String) -> Unit,
    factsEndDate: String,
    onFactsEndDateChange: (String) -> Unit,
    situationOngoing: Boolean,
    onSituationOngoingChange: (Boolean) -> Unit,
    confirmLocalDocumentAiTransfer: Boolean,
    onConfirmLocalDocumentAiTransferChange: (Boolean) -> Unit,
    onSelectOrganization: (String) -> Unit,
    chatTranscript: List<JurisChatMessage>,
    chatStatus: String,
    sending: Boolean,
    instancePreparation: String,
    preparingInstance: Boolean,
    savedSessions: List<DikeviaInstanceSession>,
    savingSession: Boolean,
    onSaveSession: (String, String, String, String) -> Unit,
    onRefreshSessions: () -> Unit,
    onPrepareInstance: (String, String) -> Unit,
    onSendQuestion: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var question by remember { mutableStateOf("") }
    var selectedInstance by remember { mutableStateOf<String?>(null) }
    var instanceObjet by remember { mutableStateOf("") }
    var sessionTitle by remember { mutableStateOf("") }
    var sessionDate by remember { mutableStateOf("") }
    var sessionMinutes by remember { mutableStateOf("") }
    var openedSession by remember { mutableStateOf<DikeviaInstanceSession?>(null) }
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val drawerScope = rememberCoroutineScope()

    MaterialTheme {
        ModalNavigationDrawer(
            drawerState = drawerState,
            gesturesEnabled = !administrationEdition,
            drawerContent = {
                if (!administrationEdition) {
                    ModalDrawerSheet {
                        Text(
                            "Dikévia — Instances",
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 22.dp),
                            color = Navy,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleLarge
                        )
                        instances.forEach { instance ->
                            NavigationDrawerItem(
                                label = {
                                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                        Text(instance.acronym, fontWeight = FontWeight.SemiBold)
                                        Text(instance.title, style = MaterialTheme.typography.bodySmall)
                                        Text(instance.description, style = MaterialTheme.typography.labelSmall, color = Color(0xFF62768A))
                                    }
                                },
                                selected = selectedInstance == instance.acronym,
                                onClick = {
                                    selectedInstance = instance.acronym
                                    instanceObjet = ""
                                    sessionTitle = ""
                                    sessionDate = ""
                                    sessionMinutes = ""
                                    drawerScope.launch { drawerState.close() }
                                },
                                modifier = Modifier.padding(horizontal = 10.dp)
                            )
                        }
                    }
                }
            }
        ) {
        Surface(modifier = modifier.fillMaxSize(), color = Glacier) {
            Column(
                modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 22.dp, vertical = 18.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("DIKÉVIA", color = Navy, fontSize = 13.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
                        Text(
                            if (administrationEdition) "Administration" else "L'assistance juridique des agents",
                            color = Navy,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    TextButton(onClick = if (authenticated) onSignOut else onSignIn) {
                        Text(if (authenticated) "Se déconnecter" else "Se connecter", color = SteelBlue)
                    }
                }

                Spacer(Modifier.height(24.dp))

                if (administrationEdition) {
                    AdminLanding()
                } else {
                    JurisOrb(
                        state = JurisOrbState.READY,
                        diameter = 148.dp,
                        modifier = Modifier.padding(top = 8.dp)
                    )
                    Spacer(Modifier.height(14.dp))
                    Text("JURIS", color = Navy, fontSize = 27.sp, fontWeight = FontWeight.Bold, letterSpacing = 3.sp)
                    Text(
                        "Votre assistant juridique territorial",
                        color = Color(0xFF52677C),
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(Modifier.height(28.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("JURIS", color = Navy, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                            Text(selectedInstance?.let { "Parcours actif : $it" } ?: "Votre assistant juridique territorial", color = Color(0xFF62768A), style = MaterialTheme.typography.bodySmall)
                        }
                        TextButton(onClick = { drawerScope.launch { drawerState.open() } }) {
                            Text("☰  Instances", color = SteelBlue, fontWeight = FontWeight.SemiBold)
                        }
                    }

                    if (selectedInstance != null) {
                        Spacer(Modifier.height(12.dp))
                        if (!authenticated || selectedOrganizationId == null) {
                            Text(
                                if (!authenticated) {
                                    "Connectez-vous pour préparer cette instance avec JURIS."
                                } else {
                                    "Aucune organisation active n'est sélectionnée pour ce compte."
                                },
                                modifier = Modifier.fillMaxWidth(),
                                color = Color(0xFF8A5A16),
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                        Text(
                            "Préparer $selectedInstance",
                            modifier = Modifier.fillMaxWidth(),
                            color = Navy,
                            fontWeight = FontWeight.SemiBold
                        )
                        OutlinedTextField(
                            value = instanceObjet,
                            onValueChange = { instanceObjet = it },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = authenticated && selectedOrganizationId != null && !preparingInstance,
                            label = { Text("Objet ou point de l'ordre du jour") },
                            placeholder = { Text("Décrivez le sujet à examiner…") },
                            minLines = 2,
                            shape = RoundedCornerShape(14.dp)
                        )
                        Spacer(Modifier.height(8.dp))
                        Button(
                            onClick = {
                                selectedInstance?.let { onPrepareInstance(it, instanceObjet.trim()) }
                            },
                            enabled = authenticated && selectedOrganizationId != null &&
                                instanceObjet.isNotBlank() && !preparingInstance,
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = SteelBlue),
                            shape = RoundedCornerShape(14.dp)
                        ) {
                            Text(if (preparingInstance) "Préparation en cours…" else "Préparer avec JURIS")
                        }
                        Spacer(Modifier.height(12.dp))
                        Text("Dossier de séance", modifier = Modifier.fillMaxWidth(), color = Navy, fontWeight = FontWeight.SemiBold)
                        OutlinedTextField(
                            value = sessionTitle,
                            onValueChange = { sessionTitle = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Intitulé du dossier") },
                            placeholder = { Text("Ex. : séance CST – organisation du temps de travail") },
                            singleLine = true,
                            shape = RoundedCornerShape(14.dp)
                        )
                        OutlinedTextField(
                            value = sessionDate,
                            onValueChange = { sessionDate = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Date de séance (facultatif)") },
                            placeholder = { Text("AAAA-MM-JJ") },
                            singleLine = true,
                            shape = RoundedCornerShape(14.dp)
                        )
                        OutlinedTextField(
                            value = sessionMinutes,
                            onValueChange = { sessionMinutes = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Compte rendu / notes de séance") },
                            placeholder = { Text("Notes de travail, décisions, réserves et suites à donner…") },
                            minLines = 3,
                            shape = RoundedCornerShape(14.dp)
                        )
                        Button(
                            onClick = {
                                val code = selectedInstance ?: return@Button
                                val title = sessionTitle.ifBlank { "$code — ${instanceObjet.take(150)}" }
                                onSaveSession(code, title, sessionDate, sessionMinutes)
                            },
                            enabled = authenticated && selectedOrganizationId != null &&
                                (sessionTitle.length >= 3 || instanceObjet.length >= 3) && !savingSession,
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = SteelBlue),
                            shape = RoundedCornerShape(14.dp)
                        ) {
                            Text(if (savingSession) "Enregistrement…" else "Enregistrer le dossier de séance")
                        }
                    }

                    if (authenticated) {
                        Spacer(Modifier.height(18.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Mes dossiers de séance", color = Navy, fontWeight = FontWeight.SemiBold)
                            TextButton(onClick = onRefreshSessions) { Text("Actualiser", color = SteelBlue) }
                        }
                        if (savedSessions.isEmpty()) {
                            Text("Aucun dossier de séance enregistré dans cette organisation.", color = Color(0xFF62768A), style = MaterialTheme.typography.bodySmall)
                        } else {
                            savedSessions.take(20).forEach { saved ->
                                Card(
                                    onClick = { openedSession = saved },
                                    modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                                    colors = CardDefaults.cardColors(containerColor = Color.White),
                                    border = androidx.compose.foundation.BorderStroke(1.dp, Border),
                                    shape = RoundedCornerShape(14.dp)
                                ) {
                                    Column(Modifier.padding(13.dp)) {
                                        Text(saved.instanceCode + " — " + saved.title, color = Navy, fontWeight = FontWeight.SemiBold)
                                        Text(
                                            "Date : " + (saved.meetingDate ?: "à fixer") + " · " + saved.meetingStatus,
                                            color = Color(0xFF62768A),
                                            style = MaterialTheme.typography.bodySmall
                                        )
                                        if (saved.minutes.isNotBlank()) {
                                            Text(saved.minutes.take(260), color = Navy, style = MaterialTheme.typography.bodySmall)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    openedSession?.let { session ->
                        AlertDialog(
                            onDismissRequest = { openedSession = null },
                            title = {
                                Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                    Text(session.instanceCode + " — " + session.title, color = Navy)
                                    Text("Dossier de séance complet", color = SteelBlue, style = MaterialTheme.typography.labelMedium)
                                }
                            },
                            text = {
                                Column(
                                    modifier = Modifier.fillMaxWidth().heightIn(max = 520.dp).verticalScroll(rememberScrollState()),
                                    verticalArrangement = Arrangement.spacedBy(12.dp)
                                ) {
                                    Text("Date de séance : " + (session.meetingDate ?: "à fixer"), color = Navy)
                                    Text("Statut : " + session.meetingStatus, color = Navy)
                                    SessionItemsSection("Ordre du jour", session.agenda)
                                    if (session.preparation.isNotBlank()) {
                                        Text("Préparation enregistrée", color = Navy, fontWeight = FontWeight.SemiBold)
                                        InstancePreparationContent(session.preparation)
                                    } else {
                                        Text("Aucune préparation juridique n'est enregistrée dans ce dossier.", color = Color(0xFF8A5A16), style = MaterialTheme.typography.bodySmall)
                                    }
                                    SessionItemsSection("Questions à traiter", session.questions)
                                    SessionItemsSection("Documents associés", session.documents)
                                    Text("Compte rendu / notes de séance", color = SteelBlue, fontWeight = FontWeight.SemiBold)
                                    Text(session.minutes.ifBlank { "Aucun compte rendu ou note n'a encore été saisi." }, color = Navy)
                                    SessionItemsSection("Actions à suivre", session.actionItems)
                                    Text("Identifiant du dossier : " + session.id, color = Color(0xFF62768A), style = MaterialTheme.typography.labelSmall)
                                }
                            },
                            confirmButton = {
                                TextButton(onClick = { openedSession = null }) { Text("Fermer") }
                            }
                        )
                    }

                    if (instancePreparation.isNotBlank() && preparationMatchesInstance(instancePreparation, selectedInstance)) {
                        Card(
                            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            border = androidx.compose.foundation.BorderStroke(1.dp, Border),
                            shape = RoundedCornerShape(16.dp)
                        ) {
                            Column(Modifier.padding(16.dp)) {
                                Text("Résultat de la préparation", color = Navy, fontWeight = FontWeight.Bold)
                                Spacer(Modifier.height(6.dp))
                                InstancePreparationContent(instancePreparation)
                                Spacer(Modifier.height(12.dp))
                                Button(
                                    onClick = { onSendQuestion(buildJurisInstancePrompt(instancePreparation)) },
                                    enabled = authenticated && selectedOrganizationId != null && !sending,
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = ButtonDefaults.buttonColors(containerColor = SteelBlue),
                                    shape = RoundedCornerShape(14.dp)
                                ) {
                                    Text(if (sending) "JURIS analyse…" else "Approfondir cette préparation avec JURIS")
                                }
                            }
                        }
                    }

                    Spacer(Modifier.height(18.dp))
                    Text("Versant de la fonction publique", modifier = Modifier.fillMaxWidth(), color = Navy, fontWeight = FontWeight.SemiBold)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("FPT" to "Territoriale", "FPE" to "État", "FPH" to "Hospitalière").forEach { (code, label) ->
                            FilterChip(
                                selected = publicService == code,
                                onClick = { onPublicServiceChange(code) },
                                label = { Text(label, fontSize = 11.sp) }
                            )
                        }
                    }
                    if (publicService == "FPT") {
                        var employerMenuExpanded by remember { mutableStateOf(false) }
                        val employerLabels = mapOf(
                            "NATIONAL" to "National / non précisé",
                            "VILLE_SAINT_ETIENNE" to "Ville de Saint-Étienne",
                            "SAINT_ETIENNE_METROPOLE" to "Saint-Étienne Métropole"
                        )
                        TextButton(onClick = { employerMenuExpanded = true }) {
                            Text("Employeur : ${employerLabels[employer] ?: employer}", color = SteelBlue)
                        }
                        DropdownMenu(expanded = employerMenuExpanded, onDismissRequest = { employerMenuExpanded = false }) {
                            employerLabels.forEach { (code, label) ->
                                DropdownMenuItem(
                                    text = { Text(label) },
                                    onClick = { onEmployerChange(code); employerMenuExpanded = false }
                                )
                            }
                        }
                    } else {
                        OutlinedTextField(
                            value = employerDetails,
                            onValueChange = onEmployerDetailsChange,
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text(if (publicService == "FPE") "Ministère ou administration (facultatif)" else "Établissement hospitalier (facultatif)") },
                            placeholder = { Text(if (publicService == "FPE") "Ministère, rectorat, préfecture…" else "Centre hospitalier, CHU…") },
                            singleLine = true,
                            shape = RoundedCornerShape(14.dp)
                        )
                    }
                    Text("Période de la situation (facultatif)", modifier = Modifier.fillMaxWidth(), color = Navy, fontWeight = FontWeight.SemiBold)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = factsStartDate,
                            onValueChange = onFactsStartDateChange,
                            modifier = Modifier.weight(1f),
                            label = { Text("Début") },
                            placeholder = { Text("AAAA-MM-JJ") },
                            singleLine = true,
                            shape = RoundedCornerShape(12.dp)
                        )
                        OutlinedTextField(
                            value = factsEndDate,
                            onValueChange = onFactsEndDateChange,
                            modifier = Modifier.weight(1f),
                            label = { Text("Fin") },
                            placeholder = { Text("AAAA-MM-JJ") },
                            enabled = !situationOngoing,
                            singleLine = true,
                            shape = RoundedCornerShape(12.dp)
                        )
                    }
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                        Checkbox(checked = situationOngoing, onCheckedChange = onSituationOngoingChange)
                        Text("La situation est toujours en cours", color = Navy, style = MaterialTheme.typography.bodySmall)
                    }
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                        Checkbox(checked = confirmLocalDocumentAiTransfer, onCheckedChange = onConfirmLocalDocumentAiTransferChange)
                        Text(
                            "Autoriser, pour cette demande, la transmission d'extraits de documents locaux au fournisseur IA",
                            color = Color(0xFF52677C),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    if (authenticated) {
                        var organizationMenuExpanded by remember { mutableStateOf(false) }
                        val selectedOrganization = organizations.firstOrNull { it.id == selectedOrganizationId }
                        Text(
                            if (selectedOrganization == null) "Aucune organisation active disponible" else "Espace : ${selectedOrganization.displayName}",
                            modifier = Modifier.fillMaxWidth(),
                            color = Navy,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                        if (organizations.size > 1) {
                            TextButton(onClick = { organizationMenuExpanded = true }) {
                                Text("Changer d'organisation", color = SteelBlue)
                            }
                            DropdownMenu(
                                expanded = organizationMenuExpanded,
                                onDismissRequest = { organizationMenuExpanded = false }
                            ) {
                                organizations.forEach { organization ->
                                    DropdownMenuItem(
                                        text = { Text(organization.displayName) },
                                        onClick = {
                                            onSelectOrganization(organization.id)
                                            organizationMenuExpanded = false
                                        }
                                    )
                                }
                            }
                        }
                    }
                    OutlinedTextField(
                        value = question,
                        onValueChange = { question = it },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = authenticated && selectedOrganizationId != null && !sending,
                        placeholder = { Text(if (authenticated) "Posez votre question à JURIS…" else "Connectez-vous pour interroger JURIS") },
                        shape = RoundedCornerShape(18.dp),
                        minLines = 2
                    )
                    Spacer(Modifier.height(10.dp))
                    Button(
                        onClick = {
                            val value = question.trim()
                            if (value.isNotEmpty()) {
                                onSendQuestion(value)
                                question = ""
                            }
                        },
                        enabled = authenticated && selectedOrganizationId != null && question.isNotBlank() && !sending,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = SteelBlue),
                        shape = RoundedCornerShape(14.dp)
                    ) {
                        Text(if (sending) "Analyse en cours…" else "Envoyer à JURIS")
                    }
                    if (chatStatus.isNotBlank()) {
                        Text(
                            chatStatus,
                            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                            color = SteelBlue,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    if (chatTranscript.isNotEmpty()) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 12.dp)
                                .heightIn(max = 360.dp)
                                .verticalScroll(rememberScrollState()),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            chatTranscript.forEachIndexed { index, message ->
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = CardDefaults.cardColors(
                                        containerColor = if (message.role == "user") Color(0xFFE7F1FA) else Color.White
                                    ),
                                    border = androidx.compose.foundation.BorderStroke(1.dp, Border),
                                    shape = RoundedCornerShape(16.dp)
                                ) {
                                    Column(Modifier.padding(16.dp)) {
                                        Text(
                                            if (message.role == "user") "Vous" else "JURIS",
                                            color = if (message.role == "user") SteelBlue else Navy,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Spacer(Modifier.height(6.dp))
                                        Text(message.content, color = Navy, style = MaterialTheme.typography.bodyMedium)
                                    }
                                }
                            }
                        }
                    }
                    if (!authenticated) {
                        Text(
                            "La connexion sécurisée est nécessaire pour accéder à vos espaces et à vos données.",
                            color = Color(0xFF62768A),
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(top = 8.dp)
                        )
                    }
                }
            }
        }
        }
    }
}

@Composable
private fun AdminLanding() {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Pilotage de Dikévia", color = Navy, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(
            "Gestion des utilisateurs, collectivités, droits et abonnements.",
            color = Color(0xFF52677C),
            style = MaterialTheme.typography.bodyMedium
        )
        listOf(
            "Utilisateurs et accès" to "Comptes, invitations et rôles",
            "Collectivités" to "Organisations et rattachements",
            "Abonnements" to "Offres, droits et facturation",
            "Supervision" to "Disponibilité et activité du service"
        ).forEach { (title, subtitle) ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Border),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(Modifier.padding(16.dp)) {
                    Text(title, color = Navy, fontWeight = FontWeight.SemiBold)
                    Text(subtitle, color = Color(0xFF62768A), style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        Text(
            "L'administration ne donne pas accès au chatbot juridique des agents.",
            color = Color(0xFF62768A),
            style = MaterialTheme.typography.bodySmall
        )
    }
}
