package com.example.firewallvoiceclient

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.navigation.compose.*
import com.example.firewallvoiceclient.ui.ChatScreen
import com.example.firewallvoiceclient.ui.LoginScreen
import com.example.firewallvoiceclient.ui.theme.FirewallVoiceClientTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            FirewallVoiceClientTheme {
                // hold server URL + API key in memory
                var serverUrl by rememberSaveable { mutableStateOf("") }
                var apiKey    by rememberSaveable { mutableStateOf("") }
                val nav = rememberNavController()

                NavHost(nav, startDestination = "login") {
                    composable("login") {
                        LoginScreen { url, key ->
                            serverUrl = url
                            apiKey    = key
                            // once logged in, drop the login screen off the backstack
                            nav.navigate("chat") {
                                popUpTo("login") { inclusive = true }
                            }
                        }
                    }
                    composable("chat") {
                        ChatScreen(
                            serverUrl = serverUrl,
                            apiKey    = apiKey
                        ) {
                            // on logout, clear and go back to login
                            serverUrl = ""
                            apiKey    = ""
                            nav.navigate("login") {
                                popUpTo("chat") { inclusive = true }
                            }
                        }
                    }
                }
            }
        }
    }
}
