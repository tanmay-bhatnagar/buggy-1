package com.buggy.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.roundToInt
import kotlin.math.sin

@Composable
fun Joystick(
    modifier: Modifier = Modifier,
    onMove: (x: Float, y: Float) -> Unit
) {
    val joystickRadius = 100.dp
    val nubRadius = 30.dp

    var center by remember { mutableStateOf(Offset.Zero) }
    var nubOffset by remember { mutableStateOf(Offset.Zero) }

    val density = LocalDensity.current
    val joystickRadiusPx = with(density) { joystickRadius.toPx() }
    val nubRadiusPx = with(density) { nubRadius.toPx() }
    val maxDragPx = joystickRadiusPx - nubRadiusPx

    Box(
        modifier = modifier
            .size(joystickRadius * 2)
            .onGloballyPositioned { coordinates ->
                center = Offset(
                    coordinates.size.width / 2f,
                    coordinates.size.height / 2f
                )
            }
            .pointerInput(Unit) {
                detectDragGestures(
                    onDragStart = { },
                    onDragEnd = {
                        nubOffset = Offset.Zero
                        onMove(0f, 0f)
                    },
                    onDragCancel = {
                        nubOffset = Offset.Zero
                        onMove(0f, 0f)
                    },
                    onDrag = { change, dragAmount ->
                        change.consume()
                        val newOffset = nubOffset + dragAmount
                        val distance = hypot(newOffset.x, newOffset.y)

                        if (distance <= maxDragPx) {
                            nubOffset = newOffset
                        } else {
                            val angle = atan2(newOffset.y, newOffset.x)
                            nubOffset = Offset(
                                x = cos(angle) * maxDragPx,
                                y = sin(angle) * maxDragPx
                            )
                        }

                        val normalizedX = nubOffset.x / maxDragPx
                        val normalizedY = -(nubOffset.y / maxDragPx)
                        onMove(normalizedX, normalizedY)
                    }
                )
            }
    ) {
        // Draw the base
        Canvas(modifier = Modifier.size(joystickRadius * 2)) {
            drawCircle(color = Color.LightGray.copy(alpha = 0.5f), radius = joystickRadiusPx)
            drawCircle(color = Color.Gray, radius = joystickRadiusPx, style = Stroke(width = 4f))
        }

        // Draw the nub
        Surface(
            shape = CircleShape,
            color = Color.DarkGray,
            modifier = Modifier
                .size(nubRadius * 2)
                .offset {
                    IntOffset(
                        x = (center.x - nubRadiusPx + nubOffset.x).roundToInt(),
                        y = (center.y - nubRadiusPx + nubOffset.y).roundToInt()
                    )
                }
        ) {}
    }
}
