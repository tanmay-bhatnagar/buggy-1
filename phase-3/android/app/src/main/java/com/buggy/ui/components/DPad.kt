package com.buggy.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun DPad(
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    onCommand: (command: String) -> Unit
) {
    Column(
        modifier = modifier
            .padding(16.dp)
            .alpha(if (enabled) 1f else 0.45f),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        DPadButton(
            icon = Icons.Default.KeyboardArrowUp,
            contentDescription = "Forward",
            command = "forward",
            enabled = enabled,
            onCommand = onCommand
        )
        
        Row(
            modifier = Modifier.padding(vertical = 16.dp),
            horizontalArrangement = Arrangement.Center
        ) {
            DPadButton(
                icon = Icons.Default.KeyboardArrowLeft,
                contentDescription = "Left",
                command = "left",
                enabled = enabled,
                onCommand = onCommand
            )
            Spacer(modifier = Modifier.width(80.dp))
            DPadButton(
                icon = Icons.Default.KeyboardArrowRight,
                contentDescription = "Right",
                command = "right",
                enabled = enabled,
                onCommand = onCommand
            )
        }
        
        DPadButton(
            icon = Icons.Default.KeyboardArrowDown,
            contentDescription = "Reverse",
            command = "reverse",
            enabled = enabled,
            onCommand = onCommand
        )
    }
}

@Composable
fun DPadButton(
    icon: ImageVector,
    contentDescription: String,
    command: String,
    enabled: Boolean,
    onCommand: (String) -> Unit
) {
    Box(
        modifier = Modifier
            .size(72.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.primary)
            .pointerInput(enabled, command) {
                detectTapGestures(
                    onPress = {
                        if (enabled) {
                            coroutineScope {
                                val repeatJob = launch {
                                    while (true) {
                                        onCommand(command)
                                        delay(150)
                                    }
                                }

                                try {
                                    tryAwaitRelease()
                                } finally {
                                    repeatJob.cancel()
                                    onCommand("stop")
                                }
                            }
                        }
                    }
                )
            },
        contentAlignment = Alignment.Center
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            tint = Color.White,
            modifier = Modifier.size(48.dp)
        )
    }
}
