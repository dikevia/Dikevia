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


data class DikeviaInstanceSession(
    val id: String,
    val instanceCode: String,
    val title: String,
    val meetingDate: String?,
    val meetingStatus: String,
    val minutes: String
)

data class DikeviaAnswer(
    val conversationId: String?,
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


    fun listInstanceSessions(accessToken: String, idToken: String, organizationId: String): List<DikeviaInstanceSession> {
        val json = request("/api/v1/instances/sessions?limit=50", "GET", accessToken, idToken, organizationId) as JSONArray
        return buildList {
            for (index in 0 until json.length()) {
                val item = json.getJSONObject(index)
                add(parseInstanceSession(item))
            }
        }
    }

    fun createInstanceSession(
        accessToken: String,
        idToken: String,
        organizationId: String,
        instanceCode: String,
        title: String,
        meetingDate: String?,
        preparation: JSONObject,
        minutes: String
    ): DikeviaInstanceSession {
        require(instanceCode in setOf("CST", "CAP", "CCP", "F3SCT"))
        require(title.trim().length in 3..200) { "L'intitulé doit contenir entre 3 et 200 caractères." }
        val payload = JSONObject()
            .put("instance_code", instanceCode)
            .put("title", title.trim())
            .put("meeting_status", "PREPARATION")
            .put("agenda", JSONArray().put(JSONObject().put("title", preparation.optString("objet", title.trim()))))
            .put("preparation", preparation)
            .put("questions", JSONArray())
            .put("documents", JSONArray())
            .put("minutes", minutes)
            .put("action_items", JSONArray())
        if (!meetingDate.isNullOrBlank()) payload.put("meeting_date", meetingDate.trim())
        val response = request("/api/v1/instances/sessions", "POST", accessToken, idToken, organizationId, payload) as JSONObject
        return parseInstanceSession(response)
    }

    fun updateInstanceSession(
        accessToken: String,
        idToken: String,
        organizationId: String,
        session: DikeviaInstanceSession,
        minutes: String
    ): DikeviaInstanceSession {
        val payload = JSONObject().put("minutes", minutes)
        val response = request(
            "/api/v1/instances/sessions/${session.id}", "PUT",
            accessToken, idToken, organizationId, payload
        ) as JSONObject
        return parseInstanceSession(response)
    }

    private fun parseInstanceSession(item: JSONObject) = DikeviaInstanceSession(
        id = item.getString("id"),
        instanceCode = item.optString("instance_code"),
        title = item.optString("title"),
        meetingDate = item.optString("meeting_date").takeIf { it.isNotBlank() && it != "null" },
        meetingStatus = item.optString("meeting_status", "PREPARATION"),
        minutes = item.optString("minutes", "")
    )

    fun prepareInstance(
        accessToken: String,
        idToken: String,
        organizationId: String,
        instance: String,
        objet: String
    ): String {
        val endpointInstance = when (instance.uppercase()) {
            "CST" -> "CST"
            "CAP" -> "CAP"
            "CCP" -> "CCP"
            "F3SCT", "FS" -> "FS"
            else -> throw IllegalArgumentException("Instance Dikévia inconnue.")
        }
        require(objet.isNotBlank()) { "Décrivez le point inscrit à l'ordre du jour." }
        val response = request(
            "/api/v1/instances/$endpointInstance/prepare",
            "POST",
            accessToken,
            idToken,
            organizationId,
            JSONObject().put("objet", objet.trim())
        ) as JSONObject
        return response.toString(2)
    }

    fun ask(
        accessToken: String,
        idToken: String,
        organizationId: String,
        question: String,
        publicService: String,
        employer: String,
        factsStartDate: String?,
        factsEndDate: String?,
        situationOngoing: Boolean,
        confirmLocalDocumentAiTransfer: Boolean,
        conversationId: String? = null
    ): DikeviaAnswer {
        require(publicService in setOf("FPT", "FPE", "FPH")) { "Versant de la fonction publique invalide." }
        require(employer.isNotBlank()) { "Précisez l'employeur ou choisissez « National / non précisé »." }
        val payload = JSONObject()
            .put("employer", employer)
            .put("public_service", publicService)
            .put("question", question)
            .put("situation_ongoing", situationOngoing)
            .put("confirm_local_document_ai_transfer", confirmLocalDocumentAiTransfer)
        if (!factsStartDate.isNullOrBlank()) payload.put("facts_start_date", factsStartDate)
        if (!factsEndDate.isNullOrBlank()) payload.put("facts_end_date", factsEndDate)
        if (!conversationId.isNullOrBlank()) payload.put("conversation_id", conversationId)
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
            conversationId = response.optString("conversation_id").takeIf { it.isNotBlank() && it != "null" },
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
