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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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

private val Glacier = Color(0xFFF3F7FB)
private val Navy = Color(0xFF17283B)
private val SteelBlue = Color(0xFF287FBD)
private val Border = Color(0xFFDCE6F0)

private data class InstanceCard(val acronym: String, val title: String, val description: String)

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
    onSendQuestion: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var question by remember { mutableStateOf("") }

    MaterialTheme {
        Surface(modifier = modifier.fillMaxSize(), color = Glacier) {
            Column(
                modifier = Modifier.fillMaxSize().padding(horizontal = 22.dp, vertical = 18.dp),
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
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        modifier = Modifier.fillMaxWidth().weight(1f, fill = false),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(instances) { instance ->
                            Card(
                                colors = CardDefaults.cardColors(containerColor = Color.White),
                                border = androidx.compose.foundation.BorderStroke(1.dp, Border),
                                shape = RoundedCornerShape(18.dp),
                                modifier = Modifier.height(126.dp)
                            ) {
                                Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                    Text(instance.acronym, color = SteelBlue, fontWeight = FontWeight.Bold, fontSize = 19.sp)
                                    Text(instance.title, color = Navy, fontWeight = FontWeight.SemiBold, fontSize = 12.sp, lineHeight = 15.sp)
                                    Text(instance.description, color = Color(0xFF62768A), fontSize = 10.sp, lineHeight = 13.sp)
                                }
                            }
                        }
                    }

                    Spacer(Modifier.height(18.dp))
                    OutlinedTextField(
                        value = question,
                        onValueChange = { question = it },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = authenticated,
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
                        enabled = authenticated && question.isNotBlank(),
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = SteelBlue),
                        shape = RoundedCornerShape(14.dp)
                    ) {
                        Text("Envoyer à JURIS")
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
