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

        // Public Auth0 Native Client ID; no client secret belongs in the APK.
        val nativeClientId = providers.gradleProperty("auth0AndroidClientId")
            .orElse("nxJSApdmOBBviDXs5WaSkkstLxYIdgWe").get()
        buildConfigField("String", "AUTH0_CLIENT_ID", "\"$nativeClientId\"")
        buildConfigField("String", "AUTH0_DOMAIN", "\"dev-brlgaz1yh2de3mjo.us.auth0.com\"")
        buildConfigField("String", "AUTH0_API_AUDIENCE", "\"https://api.dikevia.fr\"")
        buildConfigField("String", "AUTH0_OIDC_SCOPES", "\"openid profile email offline_access\"")
        manifestPlaceholders["auth0Domain"] = "dev-brlgaz1yh2de3mjo.us.auth0.com"
        manifestPlaceholders["auth0Scheme"] = "\${applicationId}.auth0"
    }

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
            // Beta APKs launch the actual Jetpack Compose implementation for native testing.
            buildConfigField("boolean", "ENABLE_NATIVE_PREVIEW", "true")
        }
        release {
            isMinifyEnabled = false
            // Keep the release launcher unchanged until native feature parity and device
            // acceptance tests are complete.
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
    implementation("com.auth0.android:auth0:3.21.3")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
