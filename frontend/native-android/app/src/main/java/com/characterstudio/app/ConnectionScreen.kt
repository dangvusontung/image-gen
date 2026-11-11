package com.characterstudio.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.launch

@androidx.compose.runtime.Composable
fun ConnectionScreen(onConnected: (String) -> Unit) {
    var origin by remember { mutableStateOf("http://127.0.0.1:8000") }
    var status by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val client = remember { BackendClient() }
    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let { origin = it; status = "QR scanned. Tap connect to verify it." }
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Character Studio", style = MaterialTheme.typography.headlineMedium)
        Text("Connect this app to the backend running on your computer.")
        OutlinedTextField(
            value = origin,
            onValueChange = { origin = it; status = null },
            label = { Text("Backend address") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(
                onClick = {
                loading = true
                status = null
                scope.launch {
                    client.check(origin).fold(
                        onSuccess = { count -> status = "Connected. $count projects found."; onConnected(origin.trim().removeSuffix("/")) },
                        onFailure = { error -> status = error.message ?: "Connection failed." },
                    )
                    loading = false
                }
                },
                enabled = !loading,
                modifier = Modifier.weight(1f),
            ) {
                if (loading) CircularProgressIndicator()
                else Text("Test and connect")
            }
            OutlinedButton(onClick = {
                scanner.launch(ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE).setPrompt("Scan backend QR code").setBeepEnabled(false))
            }) { Text("Scan QR") }
        }
        status?.let { Text(it, color = MaterialTheme.colorScheme.secondary) }
        Text("The connection is checked against both health and projects APIs before it is saved.")
    }
}
