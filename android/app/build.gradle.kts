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


dependencies {
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
