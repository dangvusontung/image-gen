package com.characterstudio.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.draw.clip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage

@Composable
internal fun ProjectPreview(origin: String, project: ProjectSummary) {
    var failed by remember(origin, project.thumbnailAssetId) { mutableStateOf(false) }
    Box(
        Modifier.size(112.dp).clip(androidx.compose.foundation.shape.RoundedCornerShape(14.dp)).background(MaterialTheme.colorScheme.surfaceContainerLow),
        contentAlignment = Alignment.Center,
    ) {
        if (project.thumbnailAssetId == null || failed) {
            Text(
                if (failed) "Preview unavailable" else "No preview yet",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(8.dp),
            )
        } else {
            AsyncImage(
                model = "$origin/api/assets/${project.thumbnailAssetId}/content",
                contentDescription = "Preview of ${project.name}",
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Fit,
                onError = { failed = true },
            )
        }
    }
}
