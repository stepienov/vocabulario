package com.vocabulario.app.di

import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.api.TokenAuthenticator
import com.vocabulario.app.data.api.TokenRefresher
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.local.TokenStore
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
    tokenStore: TokenStore,
    authenticator: TokenAuthenticator,
    tokenRefresher: TokenRefresher,
  ): OkHttpClient {
    val authInterceptor = Interceptor { chain ->
      val path = chain.request().url.encodedPath
      val token = if (path.contains("/auth/")) {
        tokenStore.peekAccessToken()
      } else {
        tokenRefresher.accessTokenForRequest()
      }
      val request = if (!token.isNullOrBlank()) {
        chain.request().newBuilder()
          .header("Authorization", "Bearer $token")
          .build()
      } else {
        chain.request()
      }
      chain.proceed(request)
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
