package fr.dikevia.commercial.designsystem

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.semantics
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Real UI state supplied by the host assistant. This component never infers
 * that the assistant is listening, searching or generating on its own.
 */
enum class JurisOrbState(val accessibilityLabel: String, val pulseDurationMs: Int) {
    READY("Assistant prêt", 3800),
    LISTENING("Entrée vocale active", 1500),
    ANALYZING("Analyse en cours", 2100),
    GENERATING("Réponse en cours de génération", 1200),
    COMPLETED("Réponse terminée", 3800),
    ERROR("Assistant indisponible ou en erreur", 2600)
}

/**
 * JARVIS visual primitive: glacier/steel/navy palette, luminous core,
 * concentric rings and restrained organic breathing.
 *
 * The caller must pass state transitions driven by actual UI/backend events.
 * Do not pass LISTENING unless microphone capture is genuinely active.
 */
@Composable
fun JurisOrb(
    state: JurisOrbState,
    modifier: Modifier = Modifier,
    diameter: Dp = 160.dp
) {
    val transition = rememberInfiniteTransition(label = "juris-orb")
    val scale by transition.animateFloat(
        initialValue = 0.96f,
        targetValue = if (state == JurisOrbState.ERROR) 1.0f else 1.045f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = state.pulseDurationMs),
            repeatMode = RepeatMode.Reverse
        ),
        label = "juris-breath"
    )
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (state == JurisOrbState.ANALYZING) 9000 else 24000
            ),
            repeatMode = RepeatMode.Restart
        ),
        label = "juris-orbit"
    )

    Box(
        modifier = modifier
            .size(diameter)
            .semantics {
                contentDescription = state.accessibilityLabel
                role = Role.Image
            },
        contentAlignment = Alignment.Center
    ) {
        Canvas(Modifier.size(diameter)) {
            val center = this.center
            val radius = size.minDimension * 0.34f
            val haloRadius = size.minDimension * 0.49f
            val coreRadius = radius * scale

            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color(0x6654B5ED),
                        Color(0x22287FBD),
                        Color.Transparent
                    ),
                    center = center,
                    radius = haloRadius
                ),
                radius = haloRadius,
                center = center
            )

            rotate(rotation, pivot = center) {
                drawCircle(
                    color = Color(0x6654B5ED),
                    radius = radius * 1.23f,
                    center = center,
                    style = Stroke(width = 1.4.dp.toPx())
                )
                drawCircle(
                    color = Color(0x33287FBD),
                    radius = radius * 1.42f,
                    center = center,
                    style = Stroke(width = 0.8.dp.toPx())
                )
            }

            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color(0xFFFFFFFF),
                        Color(0xFFBDEBFF),
                        Color(0xFF54B5ED),
                        Color(0xFF287FBD)
                    ),
                    center = center - androidx.compose.ui.geometry.Offset(
                        radius * 0.22f,
                        radius * 0.24f
                    ),
                    radius = radius * 1.55f
                ),
                radius = coreRadius,
                center = center
            )
            drawCircle(
                color = Color(0x99FFFFFF),
                radius = coreRadius * 0.18f,
                center = center - androidx.compose.ui.geometry.Offset(
                    coreRadius * 0.28f,
                    coreRadius * 0.3f
                )
            )
        }
    }
}
