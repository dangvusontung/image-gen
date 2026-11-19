package com.characterstudio.app

import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class PhotoRetrySubmissionTest {
    @Test fun failedQueueNeverDeletesOriginal() = runBlocking {
        val submission = PhotoRetrySubmission()
        var trashed = false
        runCatching { submission.submit(true, queue = { error("queue failed") }, trash = { trashed = true }) }
        assertFalse(submission.queued)
        assertFalse(trashed)
    }
    @Test fun failedCleanupCanRetryWithoutCreatingAnotherPaidGeneration() = runBlocking {
        val submission = PhotoRetrySubmission()
        var queued = 0
        var cleanup = 0
        runCatching { submission.submit(true, queue = { queued++ }, trash = { cleanup++; error("trash failed") }) }
        assertTrue(submission.queued)
        submission.submit(true, queue = { queued++ }, trash = { cleanup++ })
        assertEquals(1, queued)
        assertEquals(2, cleanup)
    }
    @Test fun uncheckedOptionKeepsOriginal() = runBlocking {
        val submission = PhotoRetrySubmission()
        var trashed = false
        submission.submit(false, queue = {}, trash = { trashed = true })
        assertTrue(submission.queued)
        assertFalse(trashed)
    }
}
