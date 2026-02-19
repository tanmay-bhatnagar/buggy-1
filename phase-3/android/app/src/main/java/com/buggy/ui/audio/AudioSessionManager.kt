package com.buggy.ui.audio

import android.content.Context
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.os.Build
import android.os.Environment
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class AudioSessionManager(context: Context) {
    private var mediaRecorder: MediaRecorder? = null
    private var mediaPlayer: MediaPlayer? = null
    
    // Create a permanent folder for the session in Documents/Jetson_Buggy/YYYY_MM_DD_HH_mm_Buggy_App_Session
    private val sessionDir = run {
        val timeStamp = SimpleDateFormat("yyyy_MM_dd_HH_mm", Locale.getDefault()).format(Date())
        val folderName = "${timeStamp}_Buggy_App_Session"
        
        val docsFolder = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)
        val buggyFolder = File(docsFolder, "Jetson_Buggy")
        if (!buggyFolder.exists()) {
            buggyFolder.mkdirs()
        }
        
        val sessionFolder = File(buggyFolder, folderName)
        if (!sessionFolder.exists()) {
            sessionFolder.mkdirs()
        }
        Log.d("AudioSession", "Session Directory: ${sessionFolder.absolutePath}")
        sessionFolder
    }
    
    private var clipCounter = 0
    private var isPlaybackActive = false
    private val appContext = context.applicationContext
    
    private val _clips = MutableStateFlow<List<File>>(emptyList())
    val clips: StateFlow<List<File>> = _clips.asStateFlow()

    fun startRecording() {
        try {
            val file = File(sessionDir, "${++clipCounter}.3gp")
            
            mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(appContext)
            } else {
                @Suppress("DEPRECATION")
                MediaRecorder()
            }.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.THREE_GPP)
                setOutputFile(file.absolutePath)
                setAudioEncoder(MediaRecorder.AudioEncoder.AMR_NB)
                prepare()
                start()
            }
            Log.d("AudioSession", "Started recording: ${file.name}")
        } catch (e: Exception) {
            Log.e("AudioSession", "Error recording: ${e.message}")
        }
    }

    fun stopRecording() {
        try {
            mediaRecorder?.apply {
                stop()
                release()
            }
            Log.d("AudioSession", "Stopped recording.")
        } catch (e: Exception) {
            Log.e("AudioSession", "Error stopping: ${e.message}")
        } finally {
            mediaRecorder = null
            // Update clips list, sorted latest first based on name
            _clips.value = sessionDir.listFiles()?.sortedByDescending { it.name.substringBefore(".3gp").toIntOrNull() ?: 0 } ?: emptyList()
        }
    }

    fun playClip(file: File, onComplete: () -> Unit) {
        if (isPlaybackActive) {
            mediaPlayer?.release()
            mediaPlayer = null
        }
        
        isPlaybackActive = true
        Log.d("AudioSession", "Playing: ${file.name}")
        try {
            mediaPlayer = MediaPlayer().apply {
                setDataSource(file.absolutePath)
                setOnCompletionListener {
                    it.release()
                    mediaPlayer = null
                    isPlaybackActive = false
                    onComplete()
                }
                prepare()
                start()
            }
        } catch (e: Exception) {
            Log.e("AudioSession", "Error playing clip: ${e.message}")
            isPlaybackActive = false
            mediaPlayer?.release()
            mediaPlayer = null
            onComplete()
        }
    }
}
