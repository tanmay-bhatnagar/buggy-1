package com.buggy.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp

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
            Spacer(modifier = Modifier.width(16.dp))
            DPadButton(
                icon = null,
                contentDescription = "Stop",
                command = "stop",
                enabled = enabled,
                isStop = true,
                onCommand = onCommand
            )
            Spacer(modifier = Modifier.width(16.dp))
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
    icon: ImageVector?,
    contentDescription: String,
    command: String,
    enabled: Boolean,
    isStop: Boolean = false,
    onCommand: (String) -> Unit
) {
    val buttonModifier = Modifier.size(72.dp)
    val content: @Composable RowScope.() -> Unit = {
        if (icon == null) {
            Text(contentDescription.uppercase())
        } else {
            Icon(
                imageVector = icon,
                contentDescription = contentDescription,
                modifier = Modifier.size(42.dp)
            )
        }
    }

    if (isStop) {
        Button(
            onClick = { onCommand(command) },
            enabled = enabled,
            modifier = buttonModifier,
            contentPadding = PaddingValues(0.dp),
            content = content
        )
    } else {
        OutlinedButton(
            onClick = { onCommand(command) },
            enabled = enabled,
            modifier = buttonModifier,
            contentPadding = PaddingValues(0.dp),
            content = content
        )
    }
}
