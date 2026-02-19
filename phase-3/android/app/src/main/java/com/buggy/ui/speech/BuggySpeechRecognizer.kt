package com.buggy.ui.speech

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

class BuggySpeechRecognizer(context: Context) {
    private var speechRecognizer: SpeechRecognizer? = null

    private val _isListening = MutableStateFlow(false)
    val isListening: StateFlow<Boolean> = _isListening.asStateFlow()

    private val _spokenText = MutableStateFlow("")
    val spokenText: StateFlow<String> = _spokenText.asStateFlow()

    init {
        if (SpeechRecognizer.isRecognitionAvailable(context)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
            speechRecognizer?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    Log.d("BuggySpeech", "Ready for speech")
                }

                override fun onBeginningOfSpeech() {
                    Log.d("BuggySpeech", "Beginning of speech")
                }

                override fun onRmsChanged(rmsdB: Float) { }

                override fun onBufferReceived(buffer: ByteArray?) { }

                override fun onEndOfSpeech() {
                    Log.d("BuggySpeech", "End of speech")
                    _isListening.value = false
                }

                override fun onError(error: Int) {
                    Log.e("BuggySpeech", "Error listening: $error")
                    _isListening.value = false
                    _spokenText.value = "Error: $error"
                }

                override fun onResults(results: Bundle?) {
                    val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        val text = matches[0]
                        Log.d("BuggySpeech", "Recognized: $text")
                        _spokenText.value = text
                    }
                    _isListening.value = false
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        _spokenText.value = matches[0]
                    }
                }

                override fun onEvent(eventType: Int, params: Bundle?) { }
            })
        } else {
            Log.e("BuggySpeech", "Speech recognition not available on this device.")
            _spokenText.value = "STT Not Available"
        }
    }

    fun startListening() {
        _isListening.value = true
        _spokenText.value = ""
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        speechRecognizer?.startListening(intent)
    }

    fun stopListening() {
        speechRecognizer?.stopListening()
        _isListening.value = false
    }

    fun destroy() {
        speechRecognizer?.destroy()
    }
}
