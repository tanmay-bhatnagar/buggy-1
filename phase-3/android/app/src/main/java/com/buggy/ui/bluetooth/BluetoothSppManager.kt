package com.buggy.ui.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException
import java.io.OutputStream
import java.util.UUID

/**
 * Real Bluetooth Classic (SPP) manager.
 *
 * Usage:
 *   val bt = BluetoothSppManager("AA:BB:CC:DD:EE:FF")
 *   bt.connect()                          // non-blocking, tries in background
 *   bt.sendCommand("""{"cmd":"move","dir":"fwd"}""")
 *   bt.disconnect()
 *
 * The Jetson must be running bt_server.py with the same SPP_UUID.
 */
@SuppressLint("MissingPermission")   // Permissions are declared in AndroidManifest
class BluetoothSppManager(
    private val targetMacAddress: String
) : IBluetoothManager {

    companion object {
        private const val TAG = "BluetoothSPP"

        /**
         * Standard SerialPortProfile UUID — must match bt_server.py on the Jetson.
         * uuid.UUID("00001101-0000-1000-8000-00805F9B34FB")
         */
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

        /** How many times to retry a failed connection before giving up. */
        private const val MAX_RETRIES = 5

        /** Delay between retry attempts (ms). */
        private const val RETRY_DELAY_MS = 3_000L
    }

    // ── State ──────────────────────────────────────────────────────────────────

    private val _isConnected = MutableStateFlow(false)
    override val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private var socket: BluetoothSocket? = null
    private var outputStream: OutputStream? = null
    private var connectJob: Job? = null

    // ── Public API ─────────────────────────────────────────────────────────────

    override fun connect() {
        if (_isConnected.value) {
            Log.d(TAG, "Already connected, ignoring connect() call")
            return
        }
        connectJob?.cancel()
        connectJob = scope.launch { connectWithRetry() }
    }

    override fun disconnect() {
        Log.d(TAG, "Disconnecting…")
        connectJob?.cancel()
        closeSocket()
        _isConnected.value = false
    }

    override fun sendCommand(command: String) {
        if (!_isConnected.value) {
            Log.w(TAG, "Not connected — dropping command: $command")
            return
        }
        scope.launch {
            try {
                // Append newline so the Jetson readline() call terminates cleanly
                outputStream?.write((command + "\n").toByteArray(Charsets.UTF_8))
                outputStream?.flush()
                Log.d(TAG, "Sent: $command")
            } catch (e: IOException) {
                Log.e(TAG, "Write failed: ${e.message}")
                _isConnected.value = false
                // Attempt reconnect after a write failure
                connectWithRetry()
            }
        }
    }

    // ── Internal helpers ───────────────────────────────────────────────────────

    private suspend fun connectWithRetry() = withContext(Dispatchers.IO) {
        val adapter = BluetoothAdapter.getDefaultAdapter()
        if (adapter == null || !adapter.isEnabled) {
            Log.e(TAG, "Bluetooth adapter not available or disabled")
            return@withContext
        }

        val device: BluetoothDevice = try {
            adapter.getRemoteDevice(targetMacAddress)
        } catch (e: IllegalArgumentException) {
            Log.e(TAG, "Invalid MAC address: $targetMacAddress")
            return@withContext
        }

        // Stop discovery — it slows down RFCOMM connections
        if (adapter.isDiscovering) adapter.cancelDiscovery()

        repeat(MAX_RETRIES) { attempt ->
            if (!isActive) return@withContext   // coroutine was cancelled

            Log.d(TAG, "Connection attempt ${attempt + 1}/$MAX_RETRIES to $targetMacAddress")

            try {
                val newSocket = device.createRfcommSocketToServiceRecord(SPP_UUID)
                newSocket.connect()             // blocking — runs on IO dispatcher
                socket = newSocket
                outputStream = newSocket.outputStream
                _isConnected.value = true
                Log.d(TAG, "Connected to $targetMacAddress")
                return@withContext              // success — exit retry loop
            } catch (e: IOException) {
                Log.w(TAG, "Attempt ${attempt + 1} failed: ${e.message}")
                closeSocket()
                if (attempt < MAX_RETRIES - 1) {
                    delay(RETRY_DELAY_MS)
                }
            }
        }

        if (!_isConnected.value) {
            Log.e(TAG, "All $MAX_RETRIES connection attempts failed")
        }
    }

    private fun closeSocket() {
        try {
            outputStream?.close()
            socket?.close()
        } catch (e: IOException) {
            Log.w(TAG, "Error closing socket: ${e.message}")
        } finally {
            outputStream = null
            socket = null
        }
    }
}
