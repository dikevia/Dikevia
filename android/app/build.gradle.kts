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
        versionCode = 1
        versionName = "0.1.0-beta"
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
