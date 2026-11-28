plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "fr.dikevia.commercial"
    compileSdk = 35

    defaultConfig {
        applicationId = "fr.dikevia.commercial"
        minSdk = 24
        targetSdk = 35
        versionCode = 3
        versionName = "0.3.0"

        // Auth0 Native Client ID is public application configuration (never a secret).
        // Keep a local Gradle override available for isolated tenant environments.
        val nativeClientId = providers.gradleProperty("auth0AndroidClientId")
            .orElse("nxJSApdmOBBviDXs5WaSkkstLxYIdgWe").get()
        buildConfigField("String", "AUTH0_CLIENT_ID", "\"$nativeClientId\"")
        buildConfigField("String", "AUTH0_DOMAIN", "\"dev-brlgaz1yh2de3mjo.us.auth0.com\"")
        buildConfigField("String", "AUTH0_API_AUDIENCE", "\"https://api.dikevia.fr\"")
        buildConfigField("String", "AUTH0_OIDC_SCOPES", "\"openid profile email offline_access\"")
        manifestPlaceholders["auth0Domain"] = "dev-brlgaz1yh2de3mjo.us.auth0.com"
        // Package-specific custom scheme avoids Samsung HTTPS App Link callback failures.
        // The manifest merger resolves ${applicationId} separately for each flavor/build type.
        manifestPlaceholders["auth0Scheme"] = "\${applicationId}.auth0"
    }

    // Deux APK indépendants, construits depuis le même socle vérifié.
    // Les deux utilisent Auth0 pour l'identité et la même API Dikévia.
    flavorDimensions += "edition"
    productFlavors {
        create("standard") {
            dimension = "edition"
            applicationId = "fr.dikevia.commercial"
            resValue("string", "app_name", "Dikévia")
            buildConfigField("String", "APP_URL", "\"https://dikevia-vector-beta-staging.onrender.com/?dikevia_app=standard\"")
        }
        create("admin") {
            dimension = "edition"
            applicationId = "fr.dikevia.admin"
            resValue("string", "app_name", "Dikévia Administration")
            buildConfigField("String", "APP_URL", "\"https://dikevia-vector-beta-staging.onrender.com/?dikevia_app=admin\"")
        }
    }

    buildFeatures {
        buildConfig = true
        compose = true
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".beta"
            versionNameSuffix = "-beta"
            // The production WebView frontend owns the complete JURIS chat pipeline,
            // including the local 384d query embedding worker and hybrid pgvector retrieval.
            // Keep the native Compose preview opt-in until it implements that same contract.
            buildConfigField("boolean", "ENABLE_NATIVE_PREVIEW", "false")
        }
        release {
            isMinifyEnabled = false
            // Keep the validated WebView launcher in release until native
            // Auth0 and API acceptance tests are completed on physical devices.
            buildConfigField("boolean", "ENABLE_NATIVE_PREVIEW", "false")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}


dependencies {
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.fragment:fragment-ktx:1.8.5")
    // Auth0.Android v3 retains support for minSdk 24; v4 requires API 26.
    implementation("com.auth0.android:auth0:3.21.3")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
