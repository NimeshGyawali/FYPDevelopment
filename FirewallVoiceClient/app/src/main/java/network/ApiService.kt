package com.example.firewallvoiceclient.network

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Credentials
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

// 1) Data model for request / response
data class Rule(
    val type: String?,
    val ip: String?,
    val port: String?,
)
data class VoiceRequest(val text: String)
data class VoiceResponse(val status: String?,       // e.g. "ok" or "unblocked_all"
                         val result: String?,       // e.g. "✅ Rule added..."
                         val rules: List<Rule>?,    // for list responses
                         val deleted: List<Rule>?,  // for unblock_all
                         val error: String? )

// 2) Retrofit interface
interface FirewallApi {
    @POST("/api/voice")
    suspend fun sendCommand(@Body req: VoiceRequest): VoiceResponse
}

// 3) Service wrapper
class ApiService private constructor(
    private val api: FirewallApi
) {
    suspend fun sendCommand(text: String): VoiceResponse =
        api.sendCommand(VoiceRequest(text))

    companion object {
        fun create(baseUrl: String, apiKey: String): ApiService {
            // Add API-key header to every request
            val authInterceptor = object : Interceptor {
                override fun intercept(chain: Interceptor.Chain): Response {
                    val orig = chain.request()
                    val req = orig.newBuilder()
                        .header("x-api-key", apiKey)
                        .build()
                    return chain.proceed(req)
                }
            }

            val client = OkHttpClient.Builder()
                .connectTimeout(60, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .callTimeout(2, TimeUnit.MINUTES)
                .addInterceptor(authInterceptor)
                .build()

            val moshi = Moshi.Builder()
                .add(KotlinJsonAdapterFactory())
                .build()

            val retrofit = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()

            return ApiService(retrofit.create(FirewallApi::class.java))
        }
    }
}
