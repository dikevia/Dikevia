plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "fr.dikevia.commercial"
    compileSdk = 35

    defaultConfig {
        applicationId = "fr.dikevia.commercial"
        minSdk = 24
        targetSdk = 35
        versionCode = 2
        versionName = "0.2.0"
    }

    // Deux APK indépendants, construits depuis le même socle vérifié.
    // Les deux conservent la même authentification Keycloak et la même API.
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
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".beta"
            versionNameSuffix = "-beta"
        }
        release {
            isMinifyEnabled = false
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
