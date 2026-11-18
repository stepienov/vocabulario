package com.vocabulario.app.di

import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.DataStoreRevocationPersistence
import com.vocabulario.app.data.session.DataStoreSessionPersistence
import com.vocabulario.app.data.session.KeystoreSessionCipher
import com.vocabulario.app.data.session.LegacyTokenSource
import com.vocabulario.app.data.session.OkHttpRefreshTransport
import com.vocabulario.app.data.session.OkHttpRevocationTransport
import com.vocabulario.app.data.session.RefreshTransport
import com.vocabulario.app.data.session.RevocationPersistence
import com.vocabulario.app.data.session.RevocationTransport
import com.vocabulario.app.data.session.SessionCipher
import com.vocabulario.app.data.session.SessionPersistence
import com.vocabulario.app.data.session.SystemWallClock
import com.vocabulario.app.data.session.WallClock
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

    @Binds
    abstract fun bindRevocationPersistence(impl: DataStoreRevocationPersistence): RevocationPersistence

    @Binds
    abstract fun bindRevocationTransport(impl: OkHttpRevocationTransport): RevocationTransport

    @Binds
    abstract fun bindWallClock(impl: SystemWallClock): WallClock
}
