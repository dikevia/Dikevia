package fr.dikevia.commercial.core.auth

import android.app.Activity
import android.content.Context
import com.auth0.android.Auth0
import com.auth0.android.authentication.AuthenticationAPIClient
import com.auth0.android.callback.Callback
import com.auth0.android.provider.WebAuthProvider
import com.auth0.android.result.Credentials
import com.auth0.android.authentication.AuthenticationException
import com.auth0.android.storage.CredentialsManagerException
import com.auth0.android.storage.SecureCredentialsManager
import com.auth0.android.storage.SharedPreferencesStorage

/**
 * Native Auth0 Authorization Code + PKCE client.
 *
 * The Native Client ID is public configuration supplied at build time.
 * No client secret is accepted or stored by this class.
 */
class Auth0NativeAuth(context: Context) {
    private val appContext = context.applicationContext
    private val account: Auth0 = Auth0.getInstance(
        BuildConfig.AUTH0_CLIENT_ID,
        BuildConfig.AUTH0_DOMAIN
    )
    private val credentialsManager = SecureCredentialsManager(
        AuthenticationAPIClient(account),
        appContext,
        SharedPreferencesStorage(appContext)
    )

    fun isConfigured(): Boolean =
        BuildConfig.AUTH0_CLIENT_ID.isNotBlank() &&
            BuildConfig.AUTH0_CLIENT_ID != "AUTH0_NATIVE_CLIENT_ID_REQUIRED" &&
            BuildConfig.AUTH0_DOMAIN.isNotBlank()

    fun login(
        activity: Activity,
        onSuccess: (Credentials) -> Unit,
        onError: (String) -> Unit
    ) {
        if (!isConfigured()) {
            onError("La connexion native n'est pas configurée : Client ID Auth0 Android manquant.")
            return
        }

        WebAuthProvider.login(account)
            .withAudience(BuildConfig.AUTH0_API_AUDIENCE)
            .withScope(BuildConfig.AUTH0_OIDC_SCOPES)
            .start(activity, object : Callback<Credentials, AuthenticationException> {
                override fun onFailure(error: AuthenticationException) {
                    // Do not expose authorization codes, tokens, or provider payloads.
                    onError(if (error.isAuthenticationCanceled) {
                        "Connexion annulée."
                    } else {
                        "Échec de l'authentification. Vérifiez la configuration Auth0 et réessayez."
                    })
                }

                override fun onSuccess(credentials: Credentials) {
                    try {
                        credentialsManager.saveCredentials(credentials)
                        onSuccess(credentials)
                    } catch (_: CredentialsManagerException) {
                        onError("La session a été obtenue mais son stockage sécurisé a échoué.")
                    }
                }
            })
    }

    fun restore(
        onSuccess: (Credentials) -> Unit,
        onUnavailable: () -> Unit
    ) {
        if (!credentialsManager.hasValidCredentials()) {
            onUnavailable()
            return
        }
        credentialsManager.getCredentials(object : Callback<Credentials, CredentialsManagerException> {
            override fun onFailure(error: CredentialsManagerException) {
                onUnavailable()
            }

            override fun onSuccess(credentials: Credentials) {
                onSuccess(credentials)
            }
        })
    }

    fun logout(
        activity: Activity,
        onComplete: () -> Unit,
        onError: (String) -> Unit
    ) {
        WebAuthProvider.logout(account)
            .start(activity, object : Callback<Void?, AuthenticationException> {
                override fun onFailure(error: AuthenticationException) {
                    onError("La déconnexion Auth0 n'a pas abouti.")
                }

                override fun onSuccess(result: Void?) {
                    credentialsManager.clearCredentials()
                    onComplete()
                }
            })
    }

    fun clearLocalSession() {
        credentialsManager.clearCredentials()
    }
}
