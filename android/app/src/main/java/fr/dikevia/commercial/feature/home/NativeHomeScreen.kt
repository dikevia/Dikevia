package fr.dikevia.commercial.feature.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import org.json.JSONObject

private val Glacier = Color(0xFFF3F7FB)
private val Navy = Color(0xFF17283B)
private val SteelBlue = Color(0xFF287FBD)
private val Border = Color(0xFFDCE6F0)

private data class InstanceCard(val acronym: String, val title: String, val description: String)

/**
 * Transfers the structured instance preparation into the existing JURIS chat.
 * This is a prompt hand-off, not a second assistant or a separate chat endpoint.
 */
private fun buildJurisInstancePrompt(rawPreparation: String): String {
    val data = runCatching { JSONObject(rawPreparation) }.getOrNull()
        ?: return "Je souhaite approfondir avec JURIS la préparation de l'instance suivante : $rawPreparation"

    val points = data.optJSONArray("points")
    val pointText = buildString {
        if (points != null) {
            for (index in 0 until minOf(points.length(), 8)) {
                val point = points.optJSONObject(index) ?: continue
                append("- ").append(point.optString("libelle")).append("\\n")
                append("  Questions : ")
                val questions = point.optJSONArray("questions")
                if (questions != null) {
                    append((0 until minOf(questions.length(), 5)).joinToString(" ; ") { questions.optString(it) })
                }
                append("\\n  Documents : ")
                val documents = point.optJSONArray("documents")
                if (documents != null) {
                    append((0 until minOf(documents.length(), 5)).joinToString(" ; ") { documents.optString(it) })
                }
                append("\\n")
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
                append("\\n")
            }
        }
    }

    return buildString {
        append("Je souhaite approfondir la préparation de mon instance avec JURIS, dans cette conversation.\\n\\n")
        append("INSTANCE : ").append(data.optString("instance")).append("\\n")
        append("OBJET : ").append(data.optString("objet")).append("\\n\\n")
        append("PISTES DE PRÉPARATION :\\n").append(pointText.ifBlank { "Aucune règle de checklist déclenchée ; analyser le sujet à partir des faits et des sources." })
        val notice = data.optString("notice")
        if (notice.isNotBlank()) append("\\nNOTICE : ").append(notice.take(500))
        if (research != null) {
            append("\\n\\nRECHERCHE JURIDIQUE : ").append(research.optString("status", "non précisée"))
            append(" ; date de référence : ").append(research.optString("requested_date", "non précisée"))
        }
        if (sourceText.isNotBlank()) append("\\nSOURCES RETOURNÉES :\\n").append(sourceText)
        append("\\nMISSION JURIS : approfondis cette préparation. Vérifie la compétence de l'instance, les textes et leur version applicable à la date des faits, ainsi que la jurisprudence pertinente. Distingue les faits déclarés des faits établis, les sources intégralement récupérées des simples métadonnées et les hypothèses des conclusions. Identifie les informations manquantes, pose les questions de clarification nécessaires, prépare des questions argumentées pour la séance et un plan d'action syndical. N'invente aucune source et ne conclus pas sans éléments suffisants.")
    }.take(5000)
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
    chatAnswer: String,
    chatStatus: String,
    sending: Boolean,
    instancePreparation: String,
    preparingInstance: Boolean,
    onPrepareInstance: (String, String) -> Unit,
    onSendQuestion: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var question by remember { mutableStateOf("") }
    var selectedInstance by remember { mutableStateOf<String?>(null) }
    var instanceObjet by remember { mutableStateOf("") }

    MaterialTheme {
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

                    Text(
                        "Préparer vos instances",
                        modifier = Modifier.fillMaxWidth(),
                        color = Navy,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.height(12.dp))
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        instances.chunked(2).forEach { pair ->
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                pair.forEach { instance ->
                                    Card(
                                        onClick = {
                                            selectedInstance = instance.acronym
                                            instanceObjet = ""
                                        },
                                        // Instance cards remain selectable before sign-in or organization selection.
                                        // Authentication and organization are required only to execute preparation.
                                        enabled = !preparingInstance,
                                        colors = CardDefaults.cardColors(containerColor = Color.White),
                                        border = androidx.compose.foundation.BorderStroke(
                                            if (selectedInstance == instance.acronym) 2.dp else 1.dp,
                                            if (selectedInstance == instance.acronym) SteelBlue else Border
                                        ),
                                        shape = RoundedCornerShape(18.dp),
                                        modifier = Modifier.weight(1f).height(126.dp)
                                    ) {
                                        Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                            Text(instance.acronym, color = SteelBlue, fontWeight = FontWeight.Bold, fontSize = 19.sp)
                                            Text(instance.title, color = Navy, fontWeight = FontWeight.SemiBold, fontSize = 12.sp, lineHeight = 15.sp)
                                            Text(instance.description, color = Color(0xFF62768A), fontSize = 10.sp, lineHeight = 13.sp)
                                        }
                                    }
                                }
                                if (pair.size == 1) Spacer(Modifier.weight(1f))
                            }
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
                    }
                    if (instancePreparation.isNotBlank()) {
                        Card(
                            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            border = androidx.compose.foundation.BorderStroke(1.dp, Border),
                            shape = RoundedCornerShape(16.dp)
                        ) {
                            Column(Modifier.padding(16.dp)) {
                                Text("Résultat de la préparation", color = Navy, fontWeight = FontWeight.Bold)
                                Spacer(Modifier.height(6.dp))
                                Text(
                                    instancePreparation,
                                    color = Navy,
                                    style = MaterialTheme.typography.bodySmall
                                )
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
                    if (chatAnswer.isNotBlank()) {
                        Card(
                            modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            border = androidx.compose.foundation.BorderStroke(1.dp, Border),
                            shape = RoundedCornerShape(16.dp)
                        ) {
                            Column(Modifier.padding(16.dp)) {
                                Text("Réponse de JURIS", color = Navy, fontWeight = FontWeight.Bold)
                                Text(chatAnswer, color = Navy, style = MaterialTheme.typography.bodyMedium)
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
