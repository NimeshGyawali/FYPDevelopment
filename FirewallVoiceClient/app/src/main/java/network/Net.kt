package com.example.firewallvoiceclient.network
import com.squareup.moshi.Moshi
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

object Net {
    private const val BASE = "http://192.168.1.100:5000"   // 👈 your PC

    private val ok = OkHttpClient.Builder()
        .addInterceptor(HttpLoggingInterceptor().setLevel(HttpLoggingInterceptor.Level.BODY))
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE)
        .addConverterFactory(MoshiConverterFactory.create(Moshi.Builder().build()))
        .client(ok)
        .build()

    val api: ApiService = retrofit.create(ApiService::class.java)
}
