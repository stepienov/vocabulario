package com.vocabulario.app.di

import com.vocabulario.app.BuildConfig
import com.vocabulario.app.data.api.TokenAuthenticator
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
  }

  @Provides
  @Singleton
  fun provideOkHttpClient(
    tokenStore: TokenStore,
    authenticator: TokenAuthenticator,
  ): OkHttpClient {
    val authInterceptor = Interceptor { chain ->
      val token = tokenStore.peekAccessToken()
      val request = if (!token.isNullOrBlank()) {
        chain.request().newBuilder()
          .addHeader("Authorization", "Bearer $token")
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
      .connectTimeout(8, TimeUnit.SECONDS)
      .readTimeout(30, TimeUnit.SECONDS)
      .writeTimeout(30, TimeUnit.SECONDS)
      .callTimeout(40, TimeUnit.SECONDS)
      .build()
  }

  @Provides
  @Singleton
  fun provideApi(client: OkHttpClient): VocabularioApi {
    val contentType = "application/json".toMediaType()
    return Retrofit.Builder()
      .baseUrl(BuildConfig.API_BASE_URL)
      .client(client)
      .addConverterFactory(json.asConverterFactory(contentType))
      .build()
      .create(VocabularioApi::class.java)
  }
}
