package fr.dikevia.commercial

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.print.PrintManager
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.Space
import android.widget.ProgressBar
import android.widget.TextView
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
    private lateinit var loadingView: LinearLayout
    private lateinit var errorView: LinearLayout
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    companion object {
        private const val APP_URL = "https://dikevia-commercial-api-l2r8.onrender.com/"
        private const val FILE_CHOOSER_REQUEST = 4107
        private val TRUSTED_HOSTS = setOf(
            "dikevia-commercial-api-l2r8.onrender.com",
            "dikevia-identity-l2r8.onrender.com"
        )
    }

    private fun isTrustedOrigin(uri: Uri): Boolean {
        val standardHttpsPort = uri.port == -1 || uri.port == 443
        val trustedHost = TRUSTED_HOSTS.any { it.equals(uri.host, ignoreCase = true) }
        return uri.scheme.equals("https", ignoreCase = true) &&
            standardHttpsPort &&
            uri.userInfo == null &&
            trustedHost
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(18, 59, 50)
        window.navigationBarColor = Color.rgb(18, 59, 50)

        webView = WebView(this)
        webView.setBackgroundColor(Color.rgb(243, 246, 244))
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
            cacheMode = WebSettings.LOAD_DEFAULT
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                safeBrowsingEnabled = true
            }
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            // The OIDC identity provider is a top-level navigation, not an embedded third-party frame.
            // Keep third-party cookies disabled; the first-party Keycloak session cookie still works.
            setAcceptThirdPartyCookies(webView, false)
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                super.onPageStarted(view, url, favicon)
                errorView.visibility = View.GONE
                loadingView.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView, url: String?) {
                super.onPageFinished(view, url)
                loadingView.visibility = View.GONE
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: android.webkit.WebResourceError
            ) {
                super.onReceivedError(view, request, error)
                if (request.isForMainFrame) showLoadError()
            }

            override fun onReceivedHttpError(
                view: WebView,
                request: WebResourceRequest,
                response: android.webkit.WebResourceResponse
            ) {
                super.onReceivedHttpError(view, request, response)
                if (request.isForMainFrame && response.statusCode >= 500) showLoadError()
            }

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                if (isTrustedOrigin(uri)) return false
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

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(243, 246, 244))
        }
        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(14, 6, 10, 6)
            setBackgroundColor(Color.rgb(18, 59, 50))
            addView(TextView(this@MainActivity).apply {
                text = "Dikévia"
                setTextColor(Color.WHITE)
                textSize = 18f
                setTypeface(null, android.graphics.Typeface.BOLD)
            }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(Button(this@MainActivity).apply {
                text = "Imprimer"
                setTextColor(Color.rgb(18, 59, 50))
                setOnClickListener { printCurrentPage() }
            })
        }
        root.addView(toolbar, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ))

        val pageContainer = FrameLayout(this)
        pageContainer.addView(webView, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))

        loadingView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.rgb(243, 246, 244))
            addView(ProgressBar(this@MainActivity))
            addView(TextView(this@MainActivity).apply {
                text = "Chargement de Dikévia…"
                setTextColor(Color.rgb(35, 59, 49))
                textSize = 15f
                setPadding(0, 16, 0, 0)
            })
        }
        pageContainer.addView(loadingView, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))

        errorView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(32, 24, 32, 24)
            setBackgroundColor(Color.rgb(243, 246, 244))
            visibility = View.GONE
            addView(TextView(this@MainActivity).apply {
                text = "Dikévia est momentanément inaccessible. Vérifiez votre connexion puis réessayez."
                setTextColor(Color.rgb(35, 59, 49))
                textSize = 16f
                gravity = Gravity.CENTER
            })
            addView(Button(this@MainActivity).apply {
                text = "Réessayer"
                setOnClickListener {
                    errorView.visibility = View.GONE
                    webView.reload()
                }
            })
        }
        pageContainer.addView(errorView, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))
        root.addView(pageContainer, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0,
            1f
        ))

        setContentView(root)
        if (savedInstanceState == null) {
            webView.loadUrl(APP_URL)
        } else if (webView.restoreState(savedInstanceState) == null) {
            webView.loadUrl(APP_URL)
        }
    }

    private fun showLoadError() {
        loadingView.visibility = View.GONE
        errorView.visibility = View.VISIBLE
    }

    private fun printCurrentPage() {
        if (!::webView.isInitialized || webView.url == null) return
        val printManager = getSystemService(PRINT_SERVICE) as PrintManager
        val adapter = webView.createPrintDocumentAdapter("Dikevia")
        printManager.print(
            "Dikévia — document",
            adapter,
            android.print.PrintAttributes.Builder().build()
        )
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