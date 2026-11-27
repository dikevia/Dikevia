package fr.dikevia.commercial

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Insets
import android.net.Uri
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.widget.FrameLayout
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    companion object {
        private val APP_URL = BuildConfig.APP_URL
        private const val FILE_CHOOSER_REQUEST = 4107
        // Only the active staging app and its Auth0 issuer stay inside the WebView.
        // Legacy Render API and Keycloak hosts must never be treated as trusted origins.
        private val TRUSTED_HOSTS = setOf(
            "dikevia-vector-beta-staging.onrender.com",
            "dev-brlgaz1yh2de3mjo.us.auth0.com"
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(234, 245, 252)
        window.navigationBarColor = Color.rgb(234, 245, 252)

        webView = WebView(this)
        webView.setBackgroundColor(Color.rgb(243, 247, 251))
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = false
            allowContentAccess = true
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            // Toujours récupérer la configuration OIDC la plus récente depuis Render.
            cacheMode = WebSettings.LOAD_NO_CACHE
            safeBrowsingEnabled = true
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, true)
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                if (uri.scheme == "https" && uri.host in TRUSTED_HOSTS) return false
                if (uri.scheme == "https" || uri.scheme == "mailto" || uri.scheme == "tel") {
                    return try {
                        startActivity(Intent(Intent.ACTION_VIEW, uri))
                        true
                    } catch (_: Exception) {
                        true
                    }
                }
                return true
            }

            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView?,
                callback: ValueCallback<Array<Uri>>?,
                params: FileChooserParams?
            ): Boolean {
                if (callback == null || params == null) return false
                filePathCallback?.onReceiveValue(null)
                filePathCallback = callback
                return try {
                    startActivityForResult(params.createIntent(), FILE_CHOOSER_REQUEST)
                    true
                } catch (_: Exception) {
                    filePathCallback?.onReceiveValue(null)
                    filePathCallback = null
                    false
                }
            }
        }

        // Android 15 (targetSdk 35) impose l'affichage edge-to-edge.
        // On réserve les zones système sans laisser la WebView passer sous les barres.
        // Le fond reste dans la palette JURIS bleu glacier.
        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.rgb(234, 245, 252))
        }
        root.addView(
            webView,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        )
        if (Build.VERSION.SDK_INT >= 35) {
            val lightSystemBars =
                WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or
                    WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
            window.insetsController?.setSystemBarsAppearance(
                lightSystemBars,
                lightSystemBars
            )
            root.setOnApplyWindowInsetsListener { _, insets ->
                val systemBarsAndCutout =
                    WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout()
                val safeInsets = insets.getInsets(systemBarsAndCutout)
                val params = webView.layoutParams as FrameLayout.LayoutParams
                params.setMargins(
                    safeInsets.left,
                    safeInsets.top,
                    safeInsets.right,
                    safeInsets.bottom
                )
                webView.layoutParams = params
                // Les insets clavier restent disponibles pour la WebView.
                WindowInsets.Builder(insets)
                    .setInsets(systemBarsAndCutout, Insets.NONE)
                    .build()
            }
        }

        // Évite qu'une ancienne configuration OIDC reste utilisée par la WebView.
        webView.clearCache(true)
        setContentView(root)
        if (Build.VERSION.SDK_INT >= 35) root.requestApplyInsets()
        if (savedInstanceState == null) {
            webView.loadUrl(APP_URL)
        } else {
            webView.restoreState(savedInstanceState)
        }
    }

    @Deprecated("Deprecated by Android; retained for WebView file selection compatibility.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != FILE_CHOOSER_REQUEST) return

        val selected = if (resultCode == RESULT_OK && data != null) {
            val clip = data.clipData
            when {
                clip != null -> Array(clip.itemCount) { index -> clip.getItemAt(index).uri }
                data.data != null -> arrayOf(data.data!!)
                else -> null
            }
        } else {
            null
        }
        filePathCallback?.onReceiveValue(selected)
        filePathCallback = null
    }

    override fun onPause() {
        // Persist OIDC session cookies before Android suspends or backgrounds the WebView.
        // This keeps the existing identity-provider session available on the next launch.
        CookieManager.getInstance().flush()
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        webView.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    @Deprecated("Deprecated by Android; use the system back dispatcher in a future UI migration.")
    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        filePathCallback?.onReceiveValue(null)
        filePathCallback = null
        if (::webView.isInitialized) {
            webView.stopLoading()
            webView.destroy()
        }
        super.onDestroy()
    }
}
