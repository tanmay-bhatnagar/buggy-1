package com.buggy.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.buggy.ui.bluetooth.IBluetoothManager
import com.buggy.ui.audio.AudioSessionManager
import com.buggy.ui.bluetooth.SimulatedBluetoothManager
import com.buggy.ui.components.DPad
import com.buggy.ui.speech.BuggySpeechRecognizer
import com.buggy.ui.ui.theme.BuggyUITheme

class MainActivity : ComponentActivity() {
    private val bluetoothManager: IBluetoothManager = SimulatedBluetoothManager()
    private lateinit var speechRecognizer: BuggySpeechRecognizer
    private lateinit var audioSessionManager: AudioSessionManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        speechRecognizer = BuggySpeechRecognizer(this)
        audioSessionManager = AudioSessionManager(this)
        enableEdgeToEdge()
        setContent {
            BuggyUITheme(darkTheme = true) {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    MainScreen(
                        modifier = Modifier.padding(innerPadding),
                        bluetoothManager = bluetoothManager,
                        speechRecognizer = speechRecognizer,
                        audioSessionManager = audioSessionManager
                    )
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        speechRecognizer.destroy()
    }
}

@Composable
fun MainScreen(modifier: Modifier = Modifier, bluetoothManager: IBluetoothManager, speechRecognizer: BuggySpeechRecognizer, audioSessionManager: AudioSessionManager) {
    val isConnected by bluetoothManager.isConnected.collectAsState()
    val isListening by speechRecognizer.isListening.collectAsState()
    val spokenText by speechRecognizer.spokenText.collectAsState()
    val clips by audioSessionManager.clips.collectAsState()
    
    LaunchedEffect(isListening) {
        if (isListening) {
            audioSessionManager.startRecording()
        } else {
            audioSessionManager.stopRecording()
        }
    }
    
    val context = LocalContext.current
    var hasRecordAudioPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { isGranted -> hasRecordAudioPermission = isGranted }
    )

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Top Bar Area: Status and Connect button
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = if (isConnected) "Status: Connected" else "Status: Disconnected",
                color = if (isConnected) Color(0xFF4CAF50) else Color(0xFFF44336),
                fontWeight = FontWeight.Bold,
                fontSize = 18.sp
            )

            Button(onClick = {
                if (isConnected) bluetoothManager.disconnect()
                else bluetoothManager.connect()
            }) {
                Text(if (isConnected) "Disconnect" else "Connect")
            }
        }

        // Camera Feed Placeholder
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .background(Color.DarkGray)
        ) {
            Text(
                text = "Camera Feed Placeholder",
                modifier = Modifier.align(Alignment.Center),
                color = Color.White
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        // STT Logic
        Text(
            text = "Voice Command", 
            fontSize = 20.sp, 
            fontWeight = FontWeight.SemiBold
        )
        Spacer(modifier = Modifier.height(8.dp))
        
        Text(
            text = if (isListening) "Listening..." else spokenText.ifEmpty { "Press mic to speak" },
            color = if (isListening) MaterialTheme.colorScheme.primary else Color.LightGray,
            textAlign = TextAlign.Center,
            modifier = Modifier.height(48.dp)
        )
        
        Spacer(modifier = Modifier.height(8.dp))

        Row(
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            FloatingActionButton(
                onClick = {
                    if (!hasRecordAudioPermission) {
                        permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    } else {
                        if (isListening) {
                            speechRecognizer.stopListening()
                        } else {
                            speechRecognizer.startListening()
                        }
                    }
                },
                shape = CircleShape,
                containerColor = if (isListening) Color.Red else MaterialTheme.colorScheme.primary
            ) {
                Icon(Icons.Filled.PlayArrow, contentDescription = "Mic", tint = Color.White)
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        Text("Session Audio Clips (Latest First)", fontSize = 14.sp, color = Color.Gray)
        Spacer(modifier = Modifier.height(8.dp))
        if (clips.isNotEmpty()) {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(horizontal = 16.dp)
            ) {
                items(clips) { clipFile ->
                    val clipNumber = clipFile.name.substringBefore(".3gp")
                    Button(onClick = { audioSessionManager.playClip(clipFile) {} }) {
                        Text(clipNumber)
                    }
                }
            }
        } else {
            Text("No audio recorded in this session yet.", fontSize = 14.sp, color = Color.DarkGray)
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Joystick Area
        Text(text = "Manual Override", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
        Spacer(modifier = Modifier.height(8.dp))

        DPad(
            onCommand = { cmd ->
                val jsonCmd = "{\"type\": \"remote\", \"direction\": \"$cmd\"}"
                bluetoothManager.sendCommand(jsonCmd)
            }
        )
    }
}