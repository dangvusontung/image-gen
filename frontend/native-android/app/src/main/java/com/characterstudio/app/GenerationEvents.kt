package com.characterstudio.app

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.buffer
import kotlinx.coroutines.flow.callbackFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import java.io.IOException
import java.util.concurrent.TimeUnit

/** The caller owns reconnection and polling fallback; cancellation closes the stream. */
internal object GenerationEvents {
    private val factory = EventSources.createFactory(OkHttpClient.Builder()
        .dispatcher(okhttp3.Dispatcher().apply { maxRequests = 128; maxRequestsPerHost = 128 })
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .build())

    fun subscribe(origin: String, projectId: String) = callbackFlow {
        var previousData: String? = null
        val source = factory.newEventSource(Request.Builder()
            .url("${origin.trimEnd('/')}/api/projects/${android.net.Uri.encode(projectId)}/jobs/events")
            .header("Accept", "text/event-stream")
            .header("Cache-Control", "no-cache")
            .build(), object : EventSourceListener() {
            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                if (type in setOf("heartbeat", "ping", "keepalive") || data.isBlank()) return
                if (previousData != data) {
                    previousData = data
                    trySend(Unit)
                }
            }
            override fun onClosed(eventSource: EventSource) { close() }
            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                close(t ?: IOException("Generation stream HTTP ${response?.code ?: "disconnected"}"))
            }
        })
        awaitClose { source.cancel() }
    }.buffer(Channel.CONFLATED)
}
