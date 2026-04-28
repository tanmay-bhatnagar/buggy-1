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
import java.util.concurrent.atomic.AtomicBoolean

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
    private val _connectionState = MutableStateFlow(BluetoothConnectionState())
    override val connectionState: StateFlow<BluetoothConnectionState> = _connectionState.asStateFlow()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private var socket: BluetoothSocket? = null
    private var outputStream: OutputStream? = null
    private var connectJob: Job? = null
    private val isConnecting = AtomicBoolean(false)

    // ── Public API ─────────────────────────────────────────────────────────────

    override fun connect() {
        if (_isConnected.value) {
            Log.d(TAG, "Already connected, ignoring connect() call")
            return
        }
        if (!isConnecting.compareAndSet(false, true)) {
            Log.d(TAG, "Connection already in progress, ignoring connect() call")
            return
        }
        connectJob = scope.launch { connectWithRetry() }
    }

    override fun disconnect() {
        Log.d(TAG, "Disconnecting…")
        connectJob?.cancel()
        closeSocket()
        isConnecting.set(false)
        _isConnected.value = false
        _connectionState.value = BluetoothConnectionState()
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
                _connectionState.value = BluetoothConnectionState(
                    BluetoothConnectionStatus.FAILED,
                    "Write failed: ${e.message ?: "socket error"}"
                )
                // Attempt reconnect after a write failure
                if (isConnecting.compareAndSet(false, true)) {
                    connectWithRetry()
                }
            }
        }
    }

    // ── Internal helpers ───────────────────────────────────────────────────────

    private suspend fun connectWithRetry() = withContext(Dispatchers.IO) {
        _connectionState.value = BluetoothConnectionState(
            BluetoothConnectionStatus.CONNECTING,
            "Connecting to $targetMacAddress..."
        )

        val adapter = BluetoothAdapter.getDefaultAdapter()
        if (adapter == null || !adapter.isEnabled) {
            Log.e(TAG, "Bluetooth adapter not available or disabled")
            _connectionState.value = BluetoothConnectionState(
                BluetoothConnectionStatus.FAILED,
                "Bluetooth is unavailable or disabled"
            )
            isConnecting.set(false)
            return@withContext
        }

        val device: BluetoothDevice = try {
            adapter.getRemoteDevice(targetMacAddress)
        } catch (e: IllegalArgumentException) {
            Log.e(TAG, "Invalid MAC address: $targetMacAddress")
            _connectionState.value = BluetoothConnectionState(
                BluetoothConnectionStatus.FAILED,
                "Invalid Bluetooth address: $targetMacAddress"
            )
            isConnecting.set(false)
            return@withContext
        }

        // Stop discovery — it slows down RFCOMM connections
        // This requires BLUETOOTH_SCAN permission; skip gracefully if not granted
        try {
            if (adapter.isDiscovering) adapter.cancelDiscovery()
        } catch (e: SecurityException) {
            Log.w(TAG, "Cannot check/cancel discovery (BLUETOOTH_SCAN not granted): ${e.message}")
        }

        try {
            repeat(MAX_RETRIES) { attempt ->
                if (!isActive) return@withContext   // coroutine was cancelled

                val attemptNumber = attempt + 1
                _connectionState.value = BluetoothConnectionState(
                    BluetoothConnectionStatus.CONNECTING,
                    "Connecting... attempt $attemptNumber/$MAX_RETRIES"
                )
                Log.d(TAG, "Connection attempt $attemptNumber/$MAX_RETRIES to $targetMacAddress")

                val lastError = connectOnce(device)
                if (_isConnected.value) {
                    _connectionState.value = BluetoothConnectionState(
                        BluetoothConnectionStatus.CONNECTED,
                        "Connected to Jetson"
                    )
                    Log.d(TAG, "Connected to $targetMacAddress")
                    return@withContext
                }

                Log.w(TAG, "Attempt $attemptNumber failed: ${lastError ?: "unknown error"}")
                if (attempt < MAX_RETRIES - 1) {
                    delay(RETRY_DELAY_MS)
                }
            }

            if (!_isConnected.value) {
                Log.e(TAG, "All $MAX_RETRIES connection attempts failed")
                _connectionState.value = BluetoothConnectionState(
                    BluetoothConnectionStatus.FAILED,
                    "Connection failed after $MAX_RETRIES attempts"
                )
            }
        } finally {
            isConnecting.set(false)
        }
    }

    private fun connectOnce(device: BluetoothDevice): String? {
        val attempts = listOf(
            "secure SPP" to { device.createRfcommSocketToServiceRecord(SPP_UUID) },
            "insecure SPP" to { device.createInsecureRfcommSocketToServiceRecord(SPP_UUID) },
            "RFCOMM channel 1" to { createRfcommSocketOnChannel(device, 1) }
        )

        var lastError: String? = null
        for ((label, socketFactory) in attempts) {
            var candidate: BluetoothSocket? = null
            try {
                Log.d(TAG, "Trying $label")
                candidate = socketFactory()
                candidate.connect()
                socket = candidate
                outputStream = candidate.outputStream
                _isConnected.value = true
                Log.d(TAG, "$label connected")
                return null
            } catch (e: Exception) {
                lastError = "$label: ${e.message ?: e.javaClass.simpleName}"
                Log.w(TAG, "$label failed: ${e.message}")
                try {
                    candidate?.close()
                } catch (closeError: IOException) {
                    Log.w(TAG, "Error closing failed $label socket: ${closeError.message}")
                }
                closeSocket()
            }
        }
        return lastError
    }

    private fun createRfcommSocketOnChannel(device: BluetoothDevice, channel: Int): BluetoothSocket {
        val method = device.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType)
        return method.invoke(device, channel) as BluetoothSocket
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
