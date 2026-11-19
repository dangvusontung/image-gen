package com.characterstudio.app

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Reconcile all projects, including those outside the loaded/search-filtered Home pages. */
internal suspend fun LibrarySession.syncHomeGeneration() = coroutineScope {
    val client = BackendClient()
    val signals = Channel<Unit>(Channel.CONFLATED)
    val streams = mutableMapOf<String, Job>()
    val requests = launch { androidx.compose.runtime.snapshotFlow { queueRevision }.collect { signals.trySend(Unit) } }
    val ticker = launch {
        while (true) {
            signals.trySend(Unit)
            delay(10_000)
        }
    }
    try {
        for (signal in signals) {
            try {
                refreshQueue()
                val summaries = client.listProjects(origin)
                val latest = summaries.associateBy { it.id }
                projects.updateItems { old -> latest[old.id] ?: old }
                val active = summaries.filter { it.activeJobs > 0 }.map { it.id }.toSet()
                streams.keys.filter { it !in active }.toList().forEach { streams.remove(it)?.cancel() }
                active.filter { streams[it]?.isActive != true }.forEach { id ->
                    streams[id] = launch {
                        try {
                            GenerationEvents.subscribe(origin, id).collect { signals.trySend(Unit) }
                        } catch (e: CancellationException) { throw e }
                        catch (_: Exception) { /* Periodic reconciliation remains available. */ }
                    }
                }
            } catch (e: CancellationException) { throw e }
            catch (_: Exception) { /* Preserve cached Home data during outages. */ }
            // Coalesce bursts from simultaneous job completions.
            delay(500)
        }
    } finally {
        requests.cancel()
        ticker.cancel()
        streams.values.forEach { it.cancel() }
        signals.close()
    }
}
