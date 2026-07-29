package com.vocabulario.app.data.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface VocabularioApi {
    @POST("auth/register")
    suspend fun register(@Body body: RegisterRequest): TokenResponse

    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @POST("auth/google")
    suspend fun googleAuth(@Body body: GoogleAuthRequest): TokenResponse

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): TokenResponse

    @GET("me")
    suspend fun me(): UserResponse

    @PUT("me")
    suspend fun updateMe(@Body body: UserUpdate): UserResponse

    @GET("me/settings")
    suspend fun getSettings(): UserSettingsResponse

    @PUT("me/settings")
    suspend fun updateSettings(@Body body: UserSettingsUpdate): UserSettingsResponse

    @GET("profiles")
    suspend fun listProfiles(): List<LanguageProfileResponse>

    @POST("profiles")
    suspend fun createProfile(@Body body: LanguageProfileCreate): LanguageProfileResponse

    @PUT("profiles/{id}")
    suspend fun updateProfile(
        @Path("id") id: String,
        @Body body: LanguageProfileUpdate,
    ): LanguageProfileResponse

    @PUT("profiles/{id}/activate")
    suspend fun activateProfile(@Path("id") id: String): LanguageProfileResponse

    @POST("lookup")
    suspend fun lookup(@Body body: LookupRequest): LookupResponse

    @POST("cards")
    suspend fun createCard(@Body body: CardCreateRequest): CardResponse

    @GET("cards")
    suspend fun listCards(@Query("profile_id") profileId: String): List<CardResponse>

    @POST("favorites")
    suspend fun addFavorite(@Body body: FavoriteCreate): FavoriteResponse

    @GET("favorites")
    suspend fun listFavorites(@Query("profile_id") profileId: String): List<FavoriteResponse>

    @GET("srs/queue")
    suspend fun srsQueue(@Query("profile_id") profileId: String): SrsQueueResponse

    @POST("srs/review")
    suspend fun srsReview(@Body body: ReviewRequest): ReviewResponse

    @POST("srs/check-answer")
    suspend fun checkAnswer(@Body body: CheckAnswerRequest): CheckAnswerResponse

    @POST("srs/distractors")
    suspend fun srsDistractors(@Body body: DistractorsRequest): DistractorsResponse
}
