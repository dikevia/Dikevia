package fr.dikevia.commercial.core.api

import fr.dikevia.commercial.BuildConfig
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URI

data class DikeviaOrganization(
    val id: String,
    val displayName: String,
    val role: String
)

data class DikeviaAnswer(
    val answer: String,
    val verificationStatus: String,
    val sources: List<String>,
    val clarificationQuestion: String?
)

/**
 * Thin Android client for the existing authenticated Dikévia API.
 * Access and ID tokens are sent only over HTTPS and are never logged or persisted here.
 */
class DikeviaApiClient {
    private val baseUrl: String = URI(BuildConfig.APP_URL).let { uri ->
        require(uri.scheme == "https" && !uri.host.isNullOrBlank()) {
            "L'URL API Dikévia doit être une origine HTTPS valide."
        }
        "${uri.scheme}://${uri.host}"
    }

    fun organizations(accessToken: String, idToken: String): List<DikeviaOrganization> {
        val json = request(
            "/api/v1/organizations",
            "GET",
            accessToken,
            idToken
        ) as JSONArray
        return buildList {
            for (index in 0 until json.length()) {
                val item = json.getJSONObject(index)
                add(
                    DikeviaOrganization(
                        id = item.getString("id"),
                        displayName = item.optString("display_name", "Organisation"),
                        role = item.optString("role", "MEMBER")
                    )
                )
            }
        }
    }

    fun ask(
        accessToken: String,
        idToken: String,
        organizationId: String,
        question: String
    ): DikeviaAnswer {
        val payload = JSONObject()
            .put("employer", "NATIONAL")
            .put("public_service", "FPT")
            .put("question", question)
        val response = request(
            "/api/v1/chat/ask",
            "POST",
            accessToken,
            idToken,
            organizationId,
            payload
        ) as JSONObject
        val sources = response.optJSONArray("sources") ?: JSONArray()
        return DikeviaAnswer(
            answer = response.optString("answer", "Aucune réponse exploitable n'a été renvoyée."),
            verificationStatus = response.optString("verification_status", "NON_VERIFIE"),
            sources = buildList {
                for (index in 0 until sources.length()) {
                    val source = sources.optJSONObject(index) ?: continue
                    val title = source.optString("title").takeIf { it.isNotBlank() } ?: continue
                    add(title)
                }
            },
            clarificationQuestion = response.optString("clarification_question")
                .takeIf { it.isNotBlank() && it != "null" }
        )
    }

    private fun request(
        path: String,
        method: String,
        accessToken: String,
        idToken: String,
        organizationId: String? = null,
        body: JSONObject? = null
    ): Any {
        require(accessToken.isNotBlank() && idToken.isNotBlank()) {
            "La session Auth0 ne contient pas les deux jetons requis."
        }
        val connection = URL(baseUrl + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 15_000
            connection.readTimeout = 45_000
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("Authorization", "Bearer $accessToken")
            connection.setRequestProperty("X-OIDC-ID-Token", idToken)
            if (organizationId != null) {
                connection.setRequestProperty("X-Organization-ID", organizationId)
            }
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val responseText = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (status !in 200..299) {
                val detail = try {
                    JSONObject(responseText).optString("detail").takeIf { it.isNotBlank() }
                } catch (_: Exception) {
                    null
                }
                throw DikeviaApiException(status, detail ?: "Le service Dikévia a refusé la requête.")
            }
            return if (responseText.trimStart().startsWith("[")) JSONArray(responseText)
            else JSONObject(responseText)
        } finally {
            connection.disconnect()
        }
    }
}

class DikeviaApiException(val statusCode: Int, message: String) : Exception(message)
