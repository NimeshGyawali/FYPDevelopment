package com.example.firewallvoiceclient.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.firewallvoiceclient.network.ApiService
import kotlinx.coroutines.launch


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    serverUrl: String,
    apiKey: String,
    onLogout: () -> Unit
) {
    val scope = rememberCoroutineScope()
    var messages by remember { mutableStateOf(listOf<Pair<String, String>>()) }
    var currentInput by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }

    Column(modifier = Modifier
        .fillMaxSize()
        .padding(16.dp)
    ) {
        // Header + Logout
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Chat", style = MaterialTheme.typography.titleLarge)
            Button(onClick = onLogout) {
                Text("Logout")
            }
        }

        Spacer(Modifier.height(8.dp))

        // Message list
        LazyColumn(modifier = Modifier.weight(1f)) {
            items(messages) { (sender, text) ->
                Text("$sender: $text", style = MaterialTheme.typography.bodyLarge)
                Spacer(Modifier.height(4.dp))
            }
        }

        Spacer(Modifier.height(8.dp))

        // Input field
        OutlinedTextField(
            value = currentInput,
            onValueChange = { currentInput = it },
            label = { Text("Enter command") },
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(Modifier.height(8.dp))

        // Send button
        Button(
            onClick = {
                val userText = currentInput.trim()
                if (userText.isEmpty()) return@Button

                // add user message
                messages = messages + ("You" to userText)
                currentInput = ""
                isLoading = true

                scope.launch {
                    try {
                        // <- here is the factory method!
                        val api = ApiService.create(serverUrl, apiKey)
                        val resp = api.sendCommand(userText)
                        val serverReply = resp.result
                            ?: resp.status
                            ?: resp.error
                            ?: "Unknown error"

                        messages = messages + ("Server" to serverReply)
                    } catch (e: Exception) {
                        messages = messages + ("Error" to (e.message ?: "Unknown"))
                    } finally {
                        isLoading = false
                    }
                }
            },
            enabled = !isLoading,
            modifier = Modifier.fillMaxWidth()
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp
                )
            } else {
                Text("Send")
            }
        }
    }
}
