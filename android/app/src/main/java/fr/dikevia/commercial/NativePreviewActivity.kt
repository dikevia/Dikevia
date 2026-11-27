package fr.dikevia.commercial

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import fr.dikevia.commercial.core.auth.Auth0NativeAuth
import fr.dikevia.commercial.feature.home.NativeHomeScreen

/**
 * Isolated native authentication/UI preview.
 * It remains outside the launcher path until the native Auth0 client and API
 * contract have been configured and validated.
 */
class NativePreviewActivity : ComponentActivity() {
    private lateinit var auth: Auth0NativeAuth
    private var authenticated by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        auth = Auth0NativeAuth(this, this)

        // Restore only from the encrypted Auth0 credentials manager.
        auth.restore(
            onSuccess = { runOnUiThread { authenticated = true } },
            onUnavailable = { runOnUiThread { authenticated = false } }
        )

        val administrationEdition = BuildConfig.FLAVOR == "admin"
        setContent {
            NativeHomeScreen(
                administrationEdition = administrationEdition,
                authenticated = authenticated,
                onSignIn = {
                    auth.login(
                        onSuccess = {
                            runOnUiThread {
                                authenticated = true
                                Toast.makeText(this, "Connexion réussie.", Toast.LENGTH_SHORT).show()
                            }
                        },
                        onError = { message ->
                            runOnUiThread {
                                Toast.makeText(this, message, Toast.LENGTH_LONG).show()
                            }
                        }
                    )
                },
                onSignOut = {
                    auth.logout(
                        onComplete = {
                            runOnUiThread {
                                authenticated = false
                                Toast.makeText(this, "Déconnexion effectuée.", Toast.LENGTH_SHORT).show()
                            }
                        },
                        onError = { message ->
                            runOnUiThread {
                                Toast.makeText(this, message, Toast.LENGTH_LONG).show()
                            }
                        }
                    )
                },
                onSendQuestion = {
                    // API integration is intentionally withheld until the native
                    // access-token and verified-ID-token contract is wired.
                    Toast.makeText(
                        this,
                        "Le service JURIS natif sera activé après raccordement sécurisé à l'API.",
                        Toast.LENGTH_LONG
                    ).show()
                }
            )
        }
    }
}
