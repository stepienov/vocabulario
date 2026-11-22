package com.vocabulario.app.data.local

import android.database.sqlite.SQLiteDatabase
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LegacyDatabaseTest {
    @Test
    fun unsupportedVersionsAreNotDestructivelyRecreated() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        for (version in 1..5) {
            val name = "legacy-migration-test-$version.db"
            context.deleteDatabase(name)
            try {
                SQLiteDatabase.openOrCreateDatabase(context.getDatabasePath(name), null).use { db ->
                    db.execSQL("CREATE TABLE preserved (value TEXT NOT NULL)")
                    db.execSQL("INSERT INTO preserved VALUES ('unsent work')")
                    db.version = version
                }
                val room = buildOfflineDatabase(context, name)
                try {
                    assertThrows(IllegalStateException::class.java) {
                        room.openHelper.writableDatabase
                    }
                } finally {
                    room.close()
                }
                SQLiteDatabase.openDatabase(
                    context.getDatabasePath(name).path, null, SQLiteDatabase.OPEN_READONLY,
                ).use { db ->
                    assertEquals(version, db.version)
                    db.rawQuery("SELECT value FROM preserved", null).use { cursor ->
                        check(cursor.moveToFirst())
                        assertEquals("unsent work", cursor.getString(0))
                    }
                }
            } finally {
                context.deleteDatabase(name)
            }
        }
    }
}
