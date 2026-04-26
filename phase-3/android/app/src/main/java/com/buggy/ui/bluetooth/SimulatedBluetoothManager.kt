package com.buggy.ui.bluetooth

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SimulatedBluetoothManager : IBluetoothManager {
    private val scope = CoroutineScope(Dispatchers.IO)
    private val _isConnected = MutableStateFlow(false)
    override val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()
    private val _connectionState = MutableStateFlow(BluetoothConnectionState())
    override val connectionState: StateFlow<BluetoothConnectionState> = _connectionState.asStateFlow()

    override fun connect() {
        Log.d("SimulatedBT", "Attempting to connect...")
        _connectionState.value = BluetoothConnectionState(BluetoothConnectionStatus.CONNECTING, "Connecting...")
        scope.launch {
            delay(1000)
            _isConnected.value = true
            _connectionState.value = BluetoothConnectionState(BluetoothConnectionStatus.CONNECTED, "Connected")
            Log.d("SimulatedBT", "Connected successfully!")
        }
    }

    override fun disconnect() {
        Log.d("SimulatedBT", "Disconnecting...")
        _isConnected.value = false
        _connectionState.value = BluetoothConnectionState()
    }

    override fun sendCommand(command: String) {
        if (_isConnected.value) {
            Log.d("SimulatedBT", "Sending command: $command")
        } else {
            Log.w("SimulatedBT", "Cannot send command, not connected. Message lost: $command")
        }
    }
}
