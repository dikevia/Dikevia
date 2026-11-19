package fr.dikevia.commercial

import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LoginScreenSmokeTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun loginScreenShowsSecureSignInAndPrivacyNotice() {
        composeRule.onNodeWithText("Dikévia").assertExists()
        composeRule.onNodeWithText("Accéder à votre espace").assertExists()
        composeRule.onNodeWithText("Se connecter").assertExists()
        composeRule.onNodeWithText("Aucun mot de passe n'est demandé ni stocké par Dikévia.").assertExists()
    }

    @Test
    fun nativeOidcConfigurationMatchesKeycloakClientContract() {
        assertEquals("dikevia-android", MainActivity.CLIENT_ID)
        assertEquals("fr.dikevia.commercial:/oauth2redirect", MainActivity.REDIRECT)
        assertTrue(MainActivity.ISSUER.endsWith("/realms/cfdt"))
    }
}
