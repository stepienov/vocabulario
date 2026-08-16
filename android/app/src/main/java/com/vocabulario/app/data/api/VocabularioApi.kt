package com.vocabulario.app.data.api

import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.Part
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

    @POST("imports/validate")
    suspend fun validateImport(@Body body: ImportValidateRequest): ImportValidateResponse

    @POST("imports/ingest")
    suspend fun ingestImport(@Body body: ImportIngestRequest): ImportValidateResponse

    @POST("imports/ingest")
    suspend fun ingestImportPreserve(@Body body: ImportIngestRequest): ImportDisplayResponse

    @Multipart
    @POST("imports/file")
    suspend fun ingestImportFile(
        @Part file: MultipartBody.Part,
        @Part("profile_id") profileId: RequestBody,
        @Part("mode") mode: RequestBody,
    ): ImportValidateResponse

    @Multipart
    @POST("imports/file")
    suspend fun ingestImportFilePreserve(
        @Part file: MultipartBody.Part,
        @Part("profile_id") profileId: RequestBody,
        @Part("mode") mode: RequestBody,
    ): ImportDisplayResponse

    @POST("imports/commit-display")
    suspend fun commitImportDisplay(@Body body: ImportDisplayCommitRequest): ImportDisplayCommitResponse

    @POST("imports/jobs")
    suspend fun createImportJob(@Body body: ImportJobCreateRequest): ImportJobProgressResponse

    @Multipart
    @POST("imports/jobs/file")
    suspend fun createImportJobFile(
        @Part file: MultipartBody.Part,
        @Part("profile_id") profileId: RequestBody,
        @Part("list_id") listId: RequestBody,
        @Part("mode") mode: RequestBody,
    ): ImportJobProgressResponse

    @GET("imports/jobs/active")
    suspend fun getActiveImportJob(@Query("profile_id") profileId: String): ImportJobProgressResponse?

    @GET("imports/jobs/{job_id}/progress")
    suspend fun getImportJobProgress(@Path("job_id") jobId: String): ImportJobProgressResponse

    @GET("imports/jobs/{job_id}")
    suspend fun getImportJob(
        @Path("job_id") jobId: String,
        @Query("include_items") includeItems: Boolean = true,
    ): ImportJobProgressResponse

    @POST("imports/jobs/{job_id}/commit")
    suspend fun commitImportJob(
        @Path("job_id") jobId: String,
        @Body body: ImportJobCommitRequest = ImportJobCommitRequest(),
    ): ImportJobProgressResponse

    @POST("imports/jobs/{job_id}/cancel")
    suspend fun cancelImportJob(@Path("job_id") jobId: String): ImportJobProgressResponse

    @POST("cards")
    suspend fun createCard(@Body body: CardCreateRequest): CardResponse

    @GET("cards")
    suspend fun listCards(@Query("profile_id") profileId: String): List<CardResponse>

    @GET("lists")
    suspend fun listWordLists(@Query("profile_id") profileId: String): List<WordListResponse>

    @POST("lists")
    suspend fun createWordList(@Body body: WordListCreate): WordListResponse

    @POST("lists/pending-inbox/ensure")
    suspend fun ensurePendingInbox(@Query("profile_id") profileId: String): WordListResponse

    @GET("lists/{list_id}/words")
    suspend fun listWords(
        @Path("list_id") listId: String,
        @Query("profile_id") profileId: String,
    ): List<CardResponse>

    @POST("lists/{list_id}/words")
    suspend fun addWordToList(
        @Path("list_id") listId: String,
        @Body body: WordListAddWordRequest,
    ): CardResponse

    @PATCH("lists/{list_id}")
    suspend fun renameWordList(
        @Path("list_id") listId: String,
        @Query("profile_id") profileId: String,
        @Body body: WordListUpdate,
    ): WordListResponse

    @DELETE("lists/{list_id}")
    suspend fun deleteWordList(
        @Path("list_id") listId: String,
        @Query("profile_id") profileId: String,
    ): retrofit2.Response<Unit>

    @DELETE("cards/{card_id}")
    suspend fun deleteCard(
        @Path("card_id") cardId: String,
        @Query("profile_id") profileId: String,
    ): retrofit2.Response<Unit>

    @POST("cards/{card_id}/move")
    suspend fun moveCard(
        @Path("card_id") cardId: String,
        @Body body: WordMoveRequest,
    ): CardResponse

    @GET("stats")
    suspend fun dashboardStats(
        @Query("profile_id") profileId: String,
        @Query("days") days: Int = 7,
    ): DashboardStatsResponse

    @GET("srs/queue")
    suspend fun srsQueue(@Query("profile_id") profileId: String): SrsQueueResponse

    @POST("srs/review")
    suspend fun srsReview(@Body body: ReviewRequest): ReviewResponse

    @POST("srs/undo")
    suspend fun srsUndo(@Body body: SrsUndoRequest): SrsUndoResponse

    @POST("srs/check-answer")
    suspend fun checkAnswer(@Body body: CheckAnswerRequest): CheckAnswerResponse

    @POST("srs/distractors")
    suspend fun srsDistractors(@Body body: DistractorsRequest): DistractorsResponse

    @GET("sync/pull")
    suspend fun syncPull(
        @Query("profile_id") profileId: String,
        @Query("since") since: String? = null,
    ): SyncPullResponse

    @POST("sync/push")
    suspend fun syncPush(@Body body: SyncPushRequest): SyncPushResponse

    @GET("corrections/quota")
    suspend fun correctionQuota(): CorrectionQuotaResponse

    @POST("cards/{card_id}/corrections")
    suspend fun createCardCorrection(
        @Path("card_id") cardId: String,
        @Query("profile_id") profileId: String,
        @Body body: CardCorrectionCreate,
    ): CardCorrectionCreateResponse

    @GET("cards/{card_id}/corrections/latest")
    suspend fun latestCardCorrection(
        @Path("card_id") cardId: String,
        @Query("profile_id") profileId: String,
    ): CardCorrectionResponse?

    @POST("cards/{card_id}/self-edit/validate")
    suspend fun validateSelfEdit(
        @Path("card_id") cardId: String,
        @Query("profile_id") profileId: String,
        @Body body: CardSelfEditRequest,
    ): SelfEditValidateResponse

    @POST("cards/{card_id}/self-edit")
    suspend fun selfEditCard(
        @Path("card_id") cardId: String,
        @Query("profile_id") profileId: String,
        @Body body: CardSelfEditRequest,
    ): CardResponse

    @GET("cards/{card_id}/history")
    suspend fun getCardHistory(
        @Path("card_id") cardId: String,
        @Query("profile_id") profileId: String,
    ): CardHistoryResponse

    @POST("cards/{card_id}/restore")
    suspend fun restoreCard(
        @Path("card_id") cardId: String,
        @Query("profile_id") profileId: String,
        @Body body: CardRestoreRequest,
    ): CardResponse

    @POST("devices/register")
    suspend fun registerDevice(@Body body: DeviceRegisterRequest): retrofit2.Response<Unit>

    @DELETE("devices/{token}")
    suspend fun unregisterDevice(@Path("token") token: String): retrofit2.Response<Unit>
}
