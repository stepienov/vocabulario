package com.vocabulario.app.di

import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.EmailVerificationGate
import com.vocabulario.app.data.api.EMAIL_VERIFICATION_REQUIRED
import com.vocabulario.app.data.api.TokenAuthenticator
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.api.isPublicAuthPath
import com.vocabulario.app.data.session.SessionCoordinator
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

  private val json = Json {
    ignoreUnknownKeys = true
    isLenient = true
    coerceInputValues = true
    encodeDefaults = true
    // Partial updates (e.g. theme only) must not send null for unset fields —
    // otherwise the API writes NULL into NOT NULL columns and the save fails.
    explicitNulls = false
  }

  @Provides
  @Singleton
  fun provideOkHttpClient(
    authenticator: TokenAuthenticator,
    sessionCoordinator: SessionCoordinator,
    verificationGate: EmailVerificationGate,
  ): OkHttpClient {
    val authInterceptor = Interceptor { chain ->
      val path = chain.request().url.encodedPath
      val token = if (isPublicAuthPath(path)) null else sessionCoordinator.accessTokenForRequest()
      val request = if (!token.isNullOrBlank()) {
        chain.request().newBuilder()
          .header("Authorization", "Bearer $token")
          .build()
      } else {
        chain.request()
      }
      val response = chain.proceed(request)
      if (response.code == 403 && !token.isNullOrBlank()) {
        val body = runCatching { response.peekBody(2048).string() }.getOrNull().orEmpty()
        if (EMAIL_VERIFICATION_REQUIRED in body) verificationGate.onServerRequired()
      }
      response
    }
    val logging = HttpLoggingInterceptor().apply {
      level = HttpLoggingInterceptor.Level.BASIC
    }
    return OkHttpClient.Builder()
      .addInterceptor(authInterceptor)
      .addInterceptor(logging)
      .authenticator(authenticator)
      .connectTimeout(15, TimeUnit.SECONDS)
      .readTimeout(180, TimeUnit.SECONDS)
      .writeTimeout(180, TimeUnit.SECONDS)
      .callTimeout(200, TimeUnit.SECONDS)
      .build()
  }

  @Provides
  @Singleton
  fun provideApi(client: OkHttpClient): VocabularioApi {
    val contentType = "application/json".toMediaType()
    return Retrofit.Builder()
      .baseUrl(ApiBaseUrl.resolve())
      .client(client)
      .addConverterFactory(json.asConverterFactory(contentType))
      .build()
      .create(VocabularioApi::class.java)
  }
}
