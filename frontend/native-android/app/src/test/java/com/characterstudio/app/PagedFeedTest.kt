package com.characterstudio.app

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test

class PagedFeedTest {
    @Test fun diskSeedIsVisibleWhileFirstNetworkRefreshRuns() {
        val scope = CoroutineScope(Dispatchers.Unconfined + SupervisorJob())
        try {
            val response = CompletableDeferred<FeedPage<Int>>()
            val feed = PagedFeed(scope, { value: Int -> value.toString() }) { response.await() }
            feed.seed(FeedPage(listOf(1), 1))
            feed.ensureLoaded()
            assertEquals(listOf(1), feed.items)
            assertTrue(feed.loading)
            response.complete(FeedPage(listOf(2), 1))
            assertEquals(listOf(2), feed.items)
            assertFalse(feed.loading)
        } finally { scope.cancel() }
    }

    @Test fun cachedReturnDoesNotFetchAgainAndPaginationStopsAtEnd() {
        val scope = CoroutineScope(Dispatchers.Unconfined + SupervisorJob())
        try {
            val offsets = mutableListOf<Int>()
            val feed = PagedFeed(scope, { value: Int -> value.toString() }) { offset ->
                offsets += offset
                if (offset == 0) FeedPage(listOf(1, 2), 3) else FeedPage(listOf(3), 3)
            }
            feed.ensureLoaded()
            feed.ensureLoaded()
            assertEquals(listOf(0), offsets)
            feed.loadMore()
            feed.loadMore()
            assertEquals(listOf(0, 2), offsets)
            assertEquals(listOf(1, 2, 3), feed.items)
            assertFalse(feed.hasMore)
        } finally { scope.cancel() }
    }

    @Test fun stalePageCannotOverwriteRefreshAndFailureKeepsCache() = runBlocking {
        val scope = CoroutineScope(Dispatchers.Unconfined + SupervisorJob())
        try {
            val old = CompletableDeferred<FeedPage<Int>>()
            var calls = 0
            val feed = PagedFeed(scope, { value: Int -> value.toString() }) {
                when (++calls) {
                    1 -> old.await()
                    2 -> FeedPage(listOf(20), 1)
                    else -> error("offline")
                }
            }
            feed.ensureLoaded()
            feed.refresh()
            old.complete(FeedPage(listOf(10), 1))
            yield()
            assertEquals(listOf(20), feed.items)
            feed.refresh()
            assertEquals(listOf(20), feed.items)
            assertEquals("offline", feed.error)
            assertFalse(feed.loading)
        } finally { scope.cancel() }
    }
}
