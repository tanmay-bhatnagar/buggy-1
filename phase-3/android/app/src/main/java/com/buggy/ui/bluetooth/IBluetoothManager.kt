package com.buggy.ui.bluetooth

import kotlinx.coroutines.flow.StateFlow

enum class BluetoothConnectionStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    FAILED
}

data class BluetoothConnectionState(
    val status: BluetoothConnectionStatus = BluetoothConnectionStatus.DISCONNECTED,
    val message: String = "Disconnected"
)

interface IBluetoothManager {
    val isConnected: StateFlow<Boolean>
    val connectionState: StateFlow<BluetoothConnectionState>
    fun connect()
    fun disconnect()
    fun sendCommand(command: String)
}
