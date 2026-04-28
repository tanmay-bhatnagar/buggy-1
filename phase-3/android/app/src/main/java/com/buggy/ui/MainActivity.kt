package com.buggy.ui

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.os.Bundle
import android.widget.ImageView
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
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
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.buggy.ui.bluetooth.BluetoothSppManager
import com.buggy.ui.bluetooth.BluetoothConnectionStatus
import com.buggy.ui.bluetooth.IBluetoothManager
import com.buggy.ui.audio.AudioSessionManager
import com.buggy.ui.components.DPad
import com.buggy.ui.speech.BuggySpeechRecognizer
import com.buggy.ui.ui.theme.BuggyUITheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : ComponentActivity() {
    // Jetson BT dongle MAC (from `hciconfig hci0` on Jetson)
    private val bluetoothManager: IBluetoothManager = BluetoothSppManager("60:FF:9E:25:25:22")
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
    val connectionState by bluetoothManager.connectionState.collectAsState()
    val isListening by speechRecognizer.isListening.collectAsState()
    val spokenText by speechRecognizer.spokenText.collectAsState()
    val isConnecting = connectionState.status == BluetoothConnectionStatus.CONNECTING
    var streamUrlInput by remember { mutableStateOf("http://192.168.1.4:8080/") }
    var activeStreamUrl by remember { mutableStateOf(streamUrlInput) }
    
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

    fun hasBluetoothRuntimePermissions(): Boolean =
        android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.S ||
            (
                ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED &&
                    ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
                )

    var hasBluetoothPermission by remember { mutableStateOf(hasBluetoothRuntimePermissions()) }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { isGranted -> hasRecordAudioPermission = isGranted }
    )

    val btPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions(),
        onResult = {
            hasBluetoothPermission = hasBluetoothRuntimePermissions()
            if (hasBluetoothPermission) {
                bluetoothManager.connect()
            }
        }
    )

    fun connectOrDisconnect() {
        if (isConnected || isConnecting) {
            bluetoothManager.disconnect()
        } else if (!hasBluetoothPermission && android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
            btPermissionLauncher.launch(
                arrayOf(
                    Manifest.permission.BLUETOOTH_CONNECT,
                    Manifest.permission.BLUETOOTH_SCAN
                )
            )
        } else {
            bluetoothManager.connect()
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        TopControlBar(
            statusText = connectionState.message,
            status = connectionState.status,
            isConnected = isConnected,
            isConnecting = isConnecting,
            streamUrlInput = streamUrlInput,
            onStreamUrlChange = { streamUrlInput = it },
            onReload = {
                activeStreamUrl = normalizeStreamUrl(streamUrlInput)
                streamUrlInput = activeStreamUrl
            },
            onConnectClick = { connectOrDisconnect() }
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            CameraFeedPanel(
                streamUrl = activeStreamUrl,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
            )

            ControlPanel(
                isConnected = isConnected,
                isListening = isListening,
                spokenText = spokenText,
                hasRecordAudioPermission = hasRecordAudioPermission,
                onMicClick = {
                    if (!hasRecordAudioPermission) {
                        permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    } else if (isListening) {
                        speechRecognizer.stopListening()
                    } else {
                        speechRecognizer.startListening()
                    }
                },
                onCommand = { cmd ->
                    val jsonCmd = "{\"type\": \"remote\", \"direction\": \"$cmd\"}"
                    bluetoothManager.sendCommand(jsonCmd)
                },
                modifier = Modifier
                    .widthIn(min = 300.dp, max = 380.dp)
                    .fillMaxHeight()
            )
        }
    }
}

@Composable
private fun TopControlBar(
    statusText: String,
    status: BluetoothConnectionStatus,
    isConnected: Boolean,
    isConnecting: Boolean,
    streamUrlInput: String,
    onStreamUrlChange: (String) -> Unit,
    onReload: () -> Unit,
    onConnectClick: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "Status: $statusText",
            color = when (status) {
                BluetoothConnectionStatus.CONNECTED -> Color(0xFF4CAF50)
                BluetoothConnectionStatus.CONNECTING -> Color(0xFFFFC107)
                BluetoothConnectionStatus.FAILED -> Color(0xFFFF7043)
                BluetoothConnectionStatus.DISCONNECTED -> Color(0xFFF44336)
            },
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp,
            modifier = Modifier.widthIn(min = 260.dp, max = 420.dp)
        )

        OutlinedTextField(
            value = streamUrlInput,
            onValueChange = onStreamUrlChange,
            singleLine = true,
            label = { Text("Camera URL") },
            modifier = Modifier.weight(1f)
        )

        Button(onClick = onReload) {
            Text("Reload")
        }

        Button(onClick = onConnectClick) {
            Text(
                when {
                    isConnected -> "Disconnect"
                    isConnecting -> "Cancel"
                    else -> "Connect"
                }
            )
        }
    }
}

@Composable
private fun ControlPanel(
    isConnected: Boolean,
    isListening: Boolean,
    spokenText: String,
    hasRecordAudioPermission: Boolean,
    onMicClick: () -> Unit,
    onCommand: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(text = "Manual Override", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(8.dp))
            DPad(enabled = isConnected, onCommand = onCommand)
        }

        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(text = "Voice Command", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = if (isListening) "Listening..." else spokenText.ifEmpty { "Press mic to speak" },
                color = if (isListening) MaterialTheme.colorScheme.primary else Color.LightGray,
                textAlign = TextAlign.Center,
                modifier = Modifier.height(48.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
            FloatingActionButton(
                onClick = onMicClick,
                shape = CircleShape,
                containerColor = if (isListening) Color.Red else MaterialTheme.colorScheme.primary
            ) {
                Icon(Icons.Filled.PlayArrow, contentDescription = "Mic", tint = Color.White)
            }
        }

        Text(
            text = if (hasRecordAudioPermission) "Mic ready" else "Mic permission needed",
            fontSize = 13.sp,
            color = Color.Gray
        )
    }
}

private fun normalizeStreamUrl(value: String): String {
    val trimmed = value.trim()
    val withScheme = if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
        trimmed
    } else {
        "http://$trimmed"
    }
    return if (withScheme.endsWith("/")) withScheme else "$withScheme/"
}

@Composable
fun CameraFeedPanel(
    streamUrl: String,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = "Camera Feed",
            fontSize = 18.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(bottom = 6.dp)
        )

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .background(Color.Black)
                .border(1.dp, Color.DarkGray),
            contentAlignment = Alignment.Center
        ) {
            SnapshotCameraImage(streamUrl = streamUrl)
        }
    }
}

@Composable
private fun SnapshotCameraImage(streamUrl: String) {
    val snapshotUrl = remember(streamUrl) { snapshotUrlFor(streamUrl) }
    var imageView by remember { mutableStateOf<ImageView?>(null) }

    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { context ->
            ImageView(context).apply {
                setBackgroundColor(android.graphics.Color.BLACK)
                scaleType = ImageView.ScaleType.FIT_CENTER
                imageView = this
            }
        },
        update = { view ->
            imageView = view
        }
    )

    LaunchedEffect(snapshotUrl, imageView) {
        val target = imageView ?: return@LaunchedEffect
        while (isActive) {
            val bitmap = withContext(Dispatchers.IO) {
                fetchBitmap(snapshotUrl)
            }
            if (bitmap != null) {
                target.setImageBitmap(bitmap)
            }
            delay(100)
        }
    }
}

private fun snapshotUrlFor(value: String): String {
    val base = normalizeStreamUrl(value)
    return when {
        base.endsWith("/snapshot.jpg") -> base
        base.endsWith("/stream/") -> base.removeSuffix("/stream/") + "/snapshot.jpg"
        else -> base + "snapshot.jpg"
    }
}

private fun fetchBitmap(url: String) = try {
    val connection = (URL(url).openConnection() as HttpURLConnection).apply {
        connectTimeout = 700
        readTimeout = 700
        useCaches = false
    }
    connection.inputStream.use { input ->
        BitmapFactory.decodeStream(input)
    }.also {
        connection.disconnect()
    }
} catch (_: Exception) {
    null
}
