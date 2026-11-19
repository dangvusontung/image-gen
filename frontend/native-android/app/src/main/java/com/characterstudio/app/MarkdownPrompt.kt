package com.characterstudio.app

import android.widget.TextView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import io.noties.markwon.Markwon

@Composable
internal fun MarkdownPrompt(prompt: String, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val markdown = remember(context) { Markwon.create(context) }
    AndroidView(modifier = modifier, factory = {
        TextView(it).apply { setTextColor(android.graphics.Color.BLACK); textSize = 14f; setTextIsSelectable(true) }
    }, update = { markdown.setMarkdown(it, prompt) })
}
