package com.buggy.ui.bluetooth

import kotlinx.coroutines.flow.StateFlow

interface IBluetoothManager {
    val isConnected: StateFlow<Boolean>
    fun connect()
    fun disconnect()
    fun sendCommand(command: String)
}
