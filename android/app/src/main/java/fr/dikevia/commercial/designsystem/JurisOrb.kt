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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * JURIS visual identity: glacier, steel and midnight blue.
 * Electric filaments are shown only while the host reports real analysis
 * or generation activity. The component does not infer backend activity.
 */
enum class JurisOrbState(val accessibilityLabel: String, val pulseDurationMs: Int) {
    READY("Assistant prêt", 3800),
    LISTENING("Entrée vocale active", 1500),
    ANALYZING("Analyse en cours", 1700),
    GENERATING("Réponse en cours de génération", 1150),
    COMPLETED("Réponse terminée", 3800),
    ERROR("Assistant indisponible ou en erreur", 2600)
}

@Composable
fun JurisOrb(
    state: JurisOrbState,
    modifier: Modifier = Modifier,
    diameter: Dp = 160.dp
) {
    val transition = rememberInfiniteTransition(label = "juris-orb")
    val active = state == JurisOrbState.ANALYZING || state == JurisOrbState.GENERATING
    val pulse by transition.animateFloat(
        initialValue = 0.965f,
        targetValue = if (active) 1.075f else 1.025f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = state.pulseDurationMs,
                easing = androidx.compose.animation.core.FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "juris-core-pulse"
    )
    val orbit by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = when (state) {
                    JurisOrbState.ANALYZING -> 6200
                    JurisOrbState.GENERATING -> 4200
                    else -> 26000
                }
            ),
            repeatMode = RepeatMode.Restart
        ),
        label = "juris-orbit"
    )
    val charge by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (state == JurisOrbState.GENERATING) 900 else 1450,
                easing = androidx.compose.animation.core.LinearEasing
            ),
            repeatMode = RepeatMode.Restart
        ),
        label = "juris-electric-charge"
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
            val c = center
            val unit = size.minDimension
            val coreRadius = unit * 0.305f * pulse
            val orbitRadius = unit * 0.385f
            val activeColor = if (state == JurisOrbState.ERROR) Color(0xFF8A9AAA) else Color(0xFF54B5ED)
            val electricColor = if (state == JurisOrbState.GENERATING) Color(0xFFBDEBFF) else Color(0xFF68B4DF)

            // Broad atmospheric halo, restrained at rest and brighter under load.
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color(0x6654B5ED).copy(alpha = if (active) 0.52f else 0.28f),
                        Color(0x33287FBD).copy(alpha = if (active) 0.42f else 0.20f),
                        Color.Transparent
                    ),
                    center = c,
                    radius = unit * if (active) 0.50f else 0.47f
                ),
                radius = unit * 0.49f,
                center = c
            )

            // Fine orbital rings with different inclinations and speeds.
            rotate(orbit, pivot = c) {
                drawCircle(
                    color = Color(0x9954B5ED),
                    radius = orbitRadius,
                    center = c,
                    style = Stroke(width = 1.25.dp.toPx())
                )
                drawArc(
                    color = Color(0xCCFFFFFF),
                    startAngle = 205f,
                    sweepAngle = 92f,
                    useCenter = false,
                    topLeft = Offset(c.x - orbitRadius * 1.12f, c.y - orbitRadius * 0.58f),
                    size = Size(orbitRadius * 2.24f, orbitRadius * 1.16f),
                    style = Stroke(width = 1.1.dp.toPx(), cap = StrokeCap.Round)
                )
            }
            rotate(-orbit * 0.58f, pivot = c) {
                drawCircle(
                    color = Color(0x4454B5ED),
                    radius = unit * 0.455f,
                    center = c,
                    style = Stroke(width = 0.8.dp.toPx())
                )
                drawArc(
                    color = Color(0xAA68B4DF),
                    startAngle = 22f,
                    sweepAngle = 62f,
                    useCenter = false,
                    topLeft = Offset(c.x - unit * 0.455f, c.y - unit * 0.455f),
                    size = Size(unit * 0.91f, unit * 0.91f),
                    style = Stroke(width = 1.5.dp.toPx(), cap = StrokeCap.Round)
                )
            }

            // Small orbiting nodes create a precise, engineered appearance.
            val nodeAngles = listOf(orbit, orbit + 142f, orbit + 258f)
            nodeAngles.forEachIndexed { index, angle ->
                val radians = angle * PI.toFloat() / 180f
                val nodeRadius = if (index == 0) orbitRadius else unit * 0.455f
                val point = Offset(
                    c.x + cos(radians) * nodeRadius,
                    c.y + sin(radians) * nodeRadius
                )
                drawCircle(
                    color = if (index == 0) Color.White else activeColor,
                    radius = if (active) 2.8.dp.toPx() else 2.dp.toPx(),
                    center = point
                )
                drawCircle(
                    color = activeColor.copy(alpha = 0.28f),
                    radius = if (active) 7.dp.toPx() else 5.dp.toPx(),
                    center = point
                )
            }

            // Electrical filaments: irregular pulses around the core, only
            // while a real analysis or generation request is active.
            if (active) {
                val arcCount = if (state == JurisOrbState.GENERATING) 4 else 3
                repeat(arcCount) { arcIndex ->
                    val baseAngle = charge * 360f + arcIndex * (360f / arcCount) + orbit * 0.22f
                    val path = Path()
                    val segments = 9
                    val startRadius = unit * 0.345f
                    for (step in 0..segments) {
                        val angle = (baseAngle + step * 4.2f) * PI.toFloat() / 180f
                        val radialJitter = when (step % 3) {
                            0 -> -unit * 0.012f
                            1 -> unit * 0.018f
                            else -> 0f
                        }
                        val radius = startRadius + radialJitter
                        val point = Offset(
                            c.x + cos(angle) * radius,
                            c.y + sin(angle) * radius
                        )
                        if (step == 0) path.moveTo(point.x, point.y) else path.lineTo(point.x, point.y)
                    }
                    drawPath(
                        path = path,
                        color = electricColor.copy(alpha = 0.22f),
                        style = Stroke(width = 6.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round)
                    )
                    drawPath(
                        path = path,
                        color = electricColor.copy(alpha = 0.92f),
                        style = Stroke(width = 1.45.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round)
                    )
                    val endAngle = (baseAngle + segments * 4.2f) * PI.toFloat() / 180f
                    val spark = Offset(
                        c.x + cos(endAngle) * startRadius,
                        c.y + sin(endAngle) * startRadius
                    )
                    drawCircle(Color.White.copy(alpha = 0.9f), radius = 2.dp.toPx(), center = spark)
                }
            }

            // Volumetric glass-like core: dark outer rim, luminous blue body,
            // cold white specular highlight and a subtle inner depth.
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFFBDEBFF), Color(0xFF287FBD), Color(0xFF17283B)),
                    center = c,
                    radius = coreRadius * 1.22f
                ),
                radius = coreRadius * 1.08f,
                center = c
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color.White,
                        Color(0xFFEAF7FF),
                        Color(0xFF8BD2F5),
                        Color(0xFF287FBD),
                        Color(0xFF17283B)
                    ),
                    center = c - Offset(coreRadius * 0.34f, coreRadius * 0.38f),
                    radius = coreRadius * 1.52f
                ),
                radius = coreRadius,
                center = c
            )
            drawCircle(
                color = Color.White.copy(alpha = 0.72f),
                radius = coreRadius * 0.16f,
                center = c - Offset(coreRadius * 0.31f, coreRadius * 0.34f)
            )
            drawCircle(
                color = Color(0xFFBDEBFF).copy(alpha = if (active) 0.78f else 0.42f),
                radius = coreRadius * 0.76f,
                center = c,
                style = Stroke(width = 0.85.dp.toPx())
            )
        }
    }
}
