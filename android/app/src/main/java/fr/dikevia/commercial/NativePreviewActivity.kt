package fr.dikevia.commercial

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import fr.dikevia.commercial.feature.home.NativeHomeScreen

/**
 * Isolated native UI preview. It is intentionally not registered as a launcher
 * activity until the dedicated Auth0 Native client and API contract are validated.
 */
class NativePreviewActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val administrationEdition = BuildConfig.FLAVOR == "admin"
        setContent {
            NativeHomeScreen(
                administrationEdition = administrationEdition,
                authenticated = false,
                onSignIn = {
                    Toast.makeText(
                        this,
                        "La configuration Auth0 native doit être validée avant activation.",
                        Toast.LENGTH_LONG
                    ).show()
                },
                onSendQuestion = {
                    // Deliberately unavailable until a verified native session exists.
                }
            )
        }
    }
}
