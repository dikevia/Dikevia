package fr.dikevia.commercial.core.api

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.view.Gravity
import android.widget.FrameLayout
import org.json.JSONObject
import java.net.URI
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

/**
 * Runs the same Transformers.js model and preprocessing as the web client,
 * inside the Android WebView. Raw text is never sent to the model host; the normal
 * chat question and the resulting 384-float vector are sent to Dikévia's API.
 *
 * Any model/network/runtime failure returns null so the API safely uses lexical
 * retrieval instead of blocking the user's question.
 */
class NativeQueryEmbeddingRuntime(
    private val activity: Activity,
    appUrl: String
) {
    private val origin = URI(appUrl).let { uri ->
        require(uri.scheme == "https" && !uri.host.isNullOrBlank()) {
            "L'URL du moteur sémantique doit utiliser HTTPS."
        }
        "${uri.scheme}://${uri.host}"
    }
    private val main = android.os.Handler(android.os.Looper.getMainLooper())
    private val sequence = AtomicLong(1L)
    private val pending = ConcurrentHashMap<Long, CompletableFuture<List<Float>?>>()
    private val texts = ConcurrentHashMap<Long, String>()
    @Volatile private var pageReady = false
    @Volatile private var disposed = false

    @SuppressLint("SetJavaScriptEnabled")
    private val webView: WebView = WebView(activity).apply {
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = false
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.allowFileAccessFromFileURLs = false
        settings.allowUniversalAccessFromFileURLs = false
        settings.javaScriptCanOpenWindowsAutomatically = false
        settings.setSupportMultipleWindows(false)
        settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
        setBackgroundColor(Color.TRANSPARENT)
        alpha = 0f
        isFocusable = false
        isFocusableInTouchMode = false
        addJavascriptInterface(Bridge(), "AndroidEmbedding")
        webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val requested = request?.url ?: return true
                return requested.scheme != "https" || requested.host != URI(origin).host
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                if (url?.startsWith("$origin/static/native-embedding.html") == true) {
                    pageReady = true
                    texts.keys.toList().forEach(::dispatch)
                }
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: android.webkit.WebResourceError?
            ) {
                super.onReceivedError(view, request, error)
                if (request?.isForMainFrame == true) {
                    failAll()
                    view?.postDelayed({ if (!disposed && !pageReady) view.reload() }, 1500)
                }
            }

            override fun onReceivedHttpError(
                view: WebView?,
                request: WebResourceRequest?,
                errorResponse: android.webkit.WebResourceResponse?
            ) {
                super.onReceivedHttpError(view, request, errorResponse)
                if (request?.isForMainFrame == true) failAll()
            }
        }
    }

    init {
        main.post {
            if (!disposed) {
                activity.addContentView(
                    webView,
                    FrameLayout.LayoutParams(1, 1, Gravity.TOP or Gravity.START)
                )
                webView.loadUrl("$origin/static/native-embedding.html")
            }
        }
    }

    fun embedBlocking(text: String): List<Float>? {
        if (disposed || text.isBlank()) return null
        val id = sequence.getAndIncrement()
        val future = CompletableFuture<List<Float>?>()
        pending[id] = future
        texts[id] = text.take(5000)
        main.post { dispatch(id) }
        return try {
            future.get(90, TimeUnit.SECONDS)
        } catch (_: Exception) {
            null
        } finally {
            pending.remove(id)
            texts.remove(id)
        }
    }

    private fun dispatch(id: Long) {
        if (!pageReady || disposed) return
        val text = texts[id] ?: return
        val script = "window.generateDikeviaEmbedding($id, ${JSONObject.quote(text)});"
        webView.evaluateJavascript(script) { result ->
            if (result != null && result.startsWith("\"Error")) {
                pending.remove(id)?.complete(null)
                texts.remove(id)
            }
        }
    }

    inner class Bridge {
        @JavascriptInterface
        fun onReady() {
            main.post {
                pageReady = true
                texts.keys.toList().forEach(::dispatch)
            }
        }

        @JavascriptInterface
        fun onResult(idValue: String, payload: String) {
            val id = idValue.toLongOrNull() ?: return
            val future = pending.remove(id) ?: return
            texts.remove(id)
            try {
                val result = JSONObject(payload)
                if (result.has("error")) {
                    future.complete(null)
                    return
                }
                val array = result.optJSONArray("embedding") ?: run {
                    future.complete(null)
                    return
                }
                if (array.length() != 384) {
                    future.complete(null)
                    return
                }
                val vector = buildList {
                    for (index in 0 until array.length()) {
                        val value = array.optDouble(index, Double.NaN)
                        if (!value.isFinite()) {
                            future.complete(null)
                            return
                        }
                        add(value.toFloat())
                    }
                }
                future.complete(vector.takeIf { it.size == 384 })
            } catch (_: Exception) {
                future.complete(null)
            }
        }

        @JavascriptInterface
        fun onRuntimeError(@Suppress("UNUSED_PARAMETER") message: String) {
            main.post {
                failAll()
                if (!disposed) webView.reload()
            }
        }
    }

    private fun failAll() {
        pageReady = false
        pending.values.forEach { it.complete(null) }
        pending.clear()
        texts.clear()
    }

    fun dispose() {
        if (disposed) return
        disposed = true
        failAll()
        main.post {
            webView.stopLoading()
            webView.removeJavascriptInterface("AndroidEmbedding")
            (webView.parent as? android.view.ViewGroup)?.removeView(webView)
            webView.destroy()
        }
    }
}
