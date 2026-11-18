package com.vocabulario.app.di

import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.DataStoreSessionPersistence
import com.vocabulario.app.data.session.KeystoreSessionCipher
import com.vocabulario.app.data.session.LegacyTokenSource
import com.vocabulario.app.data.session.OkHttpRefreshTransport
import com.vocabulario.app.data.session.RefreshTransport
import com.vocabulario.app.data.session.SessionCipher
import com.vocabulario.app.data.session.SessionPersistence
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent

@Module
@InstallIn(SingletonComponent::class)
abstract class SessionModule {

    @Binds
    abstract fun bindSessionCipher(impl: KeystoreSessionCipher): SessionCipher

    @Binds
    abstract fun bindSessionPersistence(impl: DataStoreSessionPersistence): SessionPersistence

    @Binds
    abstract fun bindRefreshTransport(impl: OkHttpRefreshTransport): RefreshTransport

    @Binds
    abstract fun bindLegacyTokenSource(impl: TokenStore): LegacyTokenSource
}
