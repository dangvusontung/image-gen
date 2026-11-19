package com.characterstudio.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
internal fun ConnectionDialog(origin: String, onDismiss: () -> Unit, onDisconnect: () -> Unit) {
    var confirmingDisconnect by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = { if (confirmingDisconnect) confirmingDisconnect = false else onDismiss() },
        title = { Text(if (confirmingDisconnect) "Disconnect from backend?" else "Connection") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Backend address", style = MaterialTheme.typography.labelMedium)
                Text(origin, style = MaterialTheme.typography.bodyMedium)
                if (confirmingDisconnect) {
                    Text("You will need to enter the backend address or scan its QR code to reconnect. Projects and images on the backend will be kept.")
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                if (confirmingDisconnect) onDisconnect() else confirmingDisconnect = true
            }) {
                Text("Disconnect", color = MaterialTheme.colorScheme.error)
            }
        },
        dismissButton = {
            TextButton(onClick = {
                if (confirmingDisconnect) confirmingDisconnect = false else onDismiss()
            }) { Text(if (confirmingDisconnect) "Cancel" else "Close") }
        },
    )
}
