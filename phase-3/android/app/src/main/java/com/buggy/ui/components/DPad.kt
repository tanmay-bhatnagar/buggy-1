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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp

@Composable
fun DPad(
    modifier: Modifier = Modifier,
    onCommand: (command: String) -> Unit
) {
    Column(
        modifier = modifier.padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        DPadButton(
            icon = Icons.Default.KeyboardArrowUp,
            contentDescription = "Forward",
            command = "forward",
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
                onCommand = onCommand
            )
            Spacer(modifier = Modifier.width(80.dp))
            DPadButton(
                icon = Icons.Default.KeyboardArrowRight,
                contentDescription = "Right",
                command = "right",
                onCommand = onCommand
            )
        }
        
        DPadButton(
            icon = Icons.Default.KeyboardArrowDown,
            contentDescription = "Reverse",
            command = "reverse",
            onCommand = onCommand
        )
    }
}

@Composable
fun DPadButton(
    icon: ImageVector,
    contentDescription: String,
    command: String,
    onCommand: (String) -> Unit
) {
    Box(
        modifier = Modifier
            .size(72.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.primary)
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        onCommand(command)
                        val released = tryAwaitRelease()
                        onCommand("stop")
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
