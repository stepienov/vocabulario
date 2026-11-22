import java.net.URI
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.dagger.hilt.android")
    id("com.google.devtools.ksp")
}

val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val apiEmulatorHost = localProps.getProperty("api.emulator.host", "10.0.2.2").trim()
val apiDeviceHost = localProps.getProperty("api.device.host", "").trim()
val apiPort = localProps.getProperty("api.port", "8000").trim()
// Pełny URL (Railway) — tylko gdy podasz -Papi.base.url=... albo api.base.url w local.properties.
// Puste = lokalny BE (Android Studio / emulator / telefon w LAN).
val apiBaseUrl = (
    (project.findProperty("api.base.url") as String?)
        ?: localProps.getProperty("api.base.url", "")
).trim().replace("\"", "")

// Build wydaniowy (AAB/APK release) wymaga jawnych parametrów; debug i CI ich nie potrzebują.
// Procedura: docs/setup/wydanie-android.md
fun releaseProp(name: String): String? =
    (project.findProperty(name) as String?)?.trim()?.takeIf { it.isNotEmpty() }

val releaseTaskRequested = gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) }
val releaseArtifactRequested = gradle.startParameter.taskNames.any {
    it.contains("release", ignoreCase = true) &&
        (it.contains("bundle", ignoreCase = true) || it.contains("assemble", ignoreCase = true))
}
val releaseApplicationId = releaseProp("release.application.id")
val releaseVersionCode = releaseProp("release.version.code")?.toIntOrNull()
val releaseVersionName = releaseProp("release.version.name")

fun isSecureApiBaseUrl(url: String): Boolean {
    val uri = runCatching { URI(url.trimEnd('/')) }.getOrNull() ?: return false
    val host = uri.host?.lowercase() ?: return false
    val localHost = host == "localhost" || !host.contains(".") ||
        host.endsWith(".local") || host.endsWith(".internal") || host.endsWith(".localhost") ||
        host.matches(Regex("""[0-9.]+""")) || host.contains(":")
    return uri.scheme == "https" && uri.userInfo == null && uri.query == null &&
        uri.fragment == null && !localHost && uri.port == -1 && uri.path == "/api/v1"
}

if (releaseTaskRequested) {
    val problems = buildList {
        if (releaseApplicationId == null || !releaseApplicationId.matches(Regex("""[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+"""))) {
            add("-Prelease.application.id=<pakiet, np. pl.firma.vocabulario>")
        }
        if (releaseVersionCode == null || releaseVersionCode < 1) add("-Prelease.version.code=<liczba całkowita >= 1>")
        if (releaseVersionName == null) add("-Prelease.version.name=<np. 0.2.0>")
        if (!isSecureApiBaseUrl(apiBaseUrl)) add("-Papi.base.url=https://<domena>/api/v1 (https, bez hosta lokalnego)")
    }
    if (problems.isNotEmpty()) {
        throw GradleException("Build release wymaga parametrów:\n  " + problems.joinToString("\n  "))
    }
}

val uploadStoreFile = releaseProp("release.keystore.file") ?: System.getenv("UPLOAD_KEYSTORE_FILE")
val uploadStorePassword = releaseProp("release.keystore.password") ?: System.getenv("UPLOAD_KEYSTORE_PASSWORD")
val uploadKeyAlias = releaseProp("release.key.alias") ?: System.getenv("UPLOAD_KEY_ALIAS")
val uploadKeyPassword = releaseProp("release.key.password") ?: System.getenv("UPLOAD_KEY_PASSWORD")
val uploadSigningReady = listOf(uploadStoreFile, uploadStorePassword, uploadKeyAlias, uploadKeyPassword).all { !it.isNullOrBlank() }
if (releaseArtifactRequested && !uploadSigningReady) {
    throw GradleException(
        "Podpis release wymaga klucza uploadu: UPLOAD_KEYSTORE_FILE, UPLOAD_KEYSTORE_PASSWORD, " +
            "UPLOAD_KEY_ALIAS, UPLOAD_KEY_PASSWORD (zmienne środowiskowe albo -Prelease.keystore.file/password, " +
            "-Prelease.key.alias/password). Klucza nie wolno trzymać w repozytorium.",
    )
}

android {
    namespace = "com.vocabulario.app"
    compileSdk = 36

    defaultConfig {
        // Debug zostaje na dotychczasowym pakiecie; release dostaje pakiet z -Prelease.application.id (patrz onVariants).
        applicationId = "com.vocabulario.app"
        minSdk = 26
        targetSdk = 36
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        versionCode = releaseVersionCode ?: 1
        versionName = releaseVersionName ?: "0.1.0"
        // Emulator vs fizyczny telefon — wybór w runtime: ApiBaseUrl.resolve()
        buildConfigField("String", "API_EMULATOR_HOST", "\"$apiEmulatorHost\"")
        buildConfigField("String", "API_DEVICE_HOST", "\"$apiDeviceHost\"")
        buildConfigField("String", "API_PORT", "\"$apiPort\"")
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
        buildConfigField(
            "String",
            "GOOGLE_WEB_CLIENT_ID",
            "\"480709179447-nf37u6tirtbbkjlisfabamm3fvrjg82l.apps.googleusercontent.com\""
        )
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    signingConfigs {
        getByName("debug") {
            storeFile = rootProject.file("keystore/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    if (uploadSigningReady) {
        signingConfigs {
            create("upload") {
                storeFile = file(uploadStoreFile!!)
                storePassword = uploadStorePassword
                keyAlias = uploadKeyAlias
                keyPassword = uploadKeyPassword
            }
        }
    }

    buildTypes {
        getByName("debug") {
            signingConfig = signingConfigs.getByName("debug")
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        getByName("release") {
            manifestPlaceholders["usesCleartextTraffic"] = "false"
            // Bez klucza uploadu release zostaje niepodpisany; nigdy nie podpisujemy go kluczem debug.
            if (uploadSigningReady) signingConfig = signingConfigs.getByName("upload")
        }
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

androidComponents {
    onVariants(selector().withBuildType("release")) { variant ->
        releaseApplicationId?.let { variant.applicationId.set(it) }
    }
}

ksp {
    // Schematy bazy pod przyszłe testy migracji Room.
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-process:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("com.google.dagger:hilt-android:2.52")
    ksp("com.google.dagger:hilt-compiler:2.52")
    implementation("androidx.hilt:hilt-navigation-compose:1.2.0")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.jakewharton.retrofit:retrofit2-kotlinx-serialization-converter:1.0.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")

    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("androidx.hilt:hilt-work:1.2.0")
    ksp("androidx.hilt:hilt-compiler:1.2.0")

    // Oficjalne FSRS (ta sama rodzina co py-fsrs na BE) — parametry ustawiamy jak w py-fsrs 6.3.x
    implementation("io.github.open-spaced-repetition:fsrs:1.0.0")

    implementation("androidx.credentials:credentials:1.3.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.3.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.1.1")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
}
