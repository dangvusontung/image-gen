package com.characterstudio.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

internal fun isGenerating(status: String) = status in setOf("queued", "submitting", "running")

@Composable
internal fun GenerationLoading() {
    CircularProgressIndicator(Modifier.size(16.dp).semantics { contentDescription = "Generation in progress" }, strokeWidth = 2.dp)
}

internal data class PendingPhoto(val id: String, val label: String)

@Composable
internal fun GeneratingPhotoPlaceholder(label: String) {
    androidx.compose.material3.Surface(color = androidx.compose.material3.MaterialTheme.colorScheme.surfaceContainerHigh) {
        androidx.compose.foundation.layout.Column(
            Modifier.then(Modifier.fillMaxWidth()).aspectRatio(1f).padding(8.dp),
            verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(10.dp, androidx.compose.ui.Alignment.CenterVertically),
            horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally,
        ) {
            GenerationLoading()
            androidx.compose.material3.Text(label, style = androidx.compose.material3.MaterialTheme.typography.labelSmall, textAlign = androidx.compose.ui.text.style.TextAlign.Center, maxLines = 2)
        }
    }
}
