package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class PosKeyNormalizeTest {
    @Test
    fun canonicalNewLookupBucketsStayCanonical() {
        assertEquals("phrase", normalizePosKey("phrase"))
        assertEquals("construction", normalizePosKey("construction"))
        assertEquals("particle", normalizePosKey("particle"))
    }

    @Test
    fun aliasesMapOntoNewBuckets() {
        assertEquals("phrase", normalizePosKey("collocation"))
        assertEquals("phrase", normalizePosKey("locution"))
        assertEquals("phrase", normalizePosKey("wyrażenie"))
        assertEquals("construction", normalizePosKey("konstrukcja"))
        assertEquals("particle", normalizePosKey("partykuła"))
        assertEquals("particle", normalizePosKey("partícula"))
    }
}
