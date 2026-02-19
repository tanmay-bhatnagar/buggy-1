package com.buggy.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.buggy.ui.bluetooth.IBluetoothManager
import com.buggy.ui.bluetooth.SimulatedBluetoothManager
import com.buggy.ui.components.Joystick
import com.buggy.ui.ui.theme.BuggyUITheme
import kotlinx.coroutines.delay

class MainActivity : ComponentActivity() {
    private val bluetoothManager: IBluetoothManager = SimulatedBluetoothManager()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            BuggyUITheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    MainScreen(
                        modifier = Modifier.padding(innerPadding),
                        bluetoothManager = bluetoothManager
                    )
                }
            }
        }
    }
}

@Composable
fun MainScreen(modifier: Modifier = Modifier, bluetoothManager: IBluetoothManager) {
    val isConnected by bluetoothManager.isConnected.collectAsState()

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

        Spacer(modifier = Modifier.height(32.dp))

        // Joystick Area
        Text(text = "Remote Control", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
        Spacer(modifier = Modifier.height(16.dp))

        Joystick(
            onMove = { x, y ->
                // x and y are -1.0 to 1.0. Up is positive y, right is positive x.
                if (x != 0f || y != 0f) {
                    val angle = (Math.toDegrees(kotlin.math.atan2(y.toDouble(), x.toDouble()))).toInt()
                    val power = (kotlin.math.hypot(x.toDouble(), y.toDouble()) * 100).toInt().coerceAtMost(100)
                    val jsonCmd = "{\"type\": \"remote\", \"power\": $power, \"angle\": $angle}"
                    bluetoothManager.sendCommand(jsonCmd)
                } else {
                    bluetoothManager.sendCommand("{\"type\": \"remote\", \"power\": 0, \"angle\": 0}")
                }
            }
        )
        
        Spacer(modifier = Modifier.height(32.dp))
    }
}