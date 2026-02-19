# Phase 3: Voice Commands Plan

## Target Hardware
**Primary Deployment:** Samsung Galaxy S26 Ultra (Top Variant)
- **Reference Specs:** Snapdragon 8 Gen 4 / Gen 5 for Galaxy (massive NPU capabilities)
- **RAM:** 12GB - 16GB LPDDR5X
- **Compute:** Extremely capable of running large on-device AI models with near-zero latency.

**Interim Testing Device:** Samsung Galaxy Tab S7
- **Specs:** Snapdragon 865+, 6GB-8GB RAM
- **Testing Plan:**
  - **Native STT (Option 1):** Will run flawlessly. The native Google/Samsung recognizer is highly optimized.
  - **Bluetooth & UI:** Full testing works perfectly here.
  - **SLM Layer:** We will run a heavily quantized (4-bit), 1.5B or 2B parameter edge model natively on the Tab S7. It may take a couple of seconds longer to parse commands compared to the S26 Ultra, but it will allow us to test the entire end-to-end pipeline **100% locally and offline**.

## Speech-to-Text (STT) Options for Android

Given the extreme power of this device, we have three great options for translating your voice into JSON commands for the Jetson over Bluetooth.

### Option 1: Android Native `SpeechRecognizer` (Recommended)
Modern Samsung flagships feature incredible, built-in, on-device speech recognition powered by Google.
*   **Pros:** Zero setup, adds 0MB to your app size, heavily optimized for the device's NPU, extremely low battery usage, handles background noise very well.
*   **Cons:** You rely on the OS. Sometimes it pauses if it thinks you're done speaking.
*   **Verdict:** This should be our primary choice for basic commands ("forward", "stop", "follow me").

### Option 2: Whisper.cpp (whisper.android)
A C++ port of OpenAI's Whisper model running directly on your phone.
*   **Pros:** The gold standard for accuracy. Incredibly robust to wind, background noise, and accents. We could run the `base.en` (142MB) or even `small.en` model effortlessly on an S26 Ultra.
*   **Cons:** Requires importing gigabytes of NDK/C++ build tools into our Android Studio project. Higher latency (usually ~500ms - 1s delay before the command sends).
*   **Verdict:** Great if we find the native Google STT isn't accurate enough for specific robotic terminology.

## Current Strategy: Option 1 (Android Native)

We are actively progressing with **Option 1: Android Native `SpeechRecognizer`**. It is the most robust, battery-efficient, and cleanly integrated method for modern Android devices. We will use the native STT engine to constantly listen (when activated) and capture speech payloads.

### Backpocket Alternatives
If we discover that the native Android recognizer struggles with robotic commands or offline operation in edge environments, we have two fallback architectures:
*   **Fallback A (Whisper.cpp):** Port OpenAI's Whisper `small.en` model directly onto the device for unparalleled accuracy at the cost of latency.
*   **Fallback B (Vosk):** Use Vosk's lightweight models for continuous, offline keyword spotting.

---

## Debugging: Audio Session Storage

Because the STT -> SLM pipeline will inevitably have edge causes and misinterpretations, we have implemented an **Audio Session Manager**.
*   **Persistent Storage:** Every time you use a voice command, the raw audio is recorded.
*   **Directory Structure:** The `.3gp` audio clips are saved permanently to your device's core Documents folder under: `Documents/Jetson_Buggy/YYYY_MM_DD_HH_mm_Buggy_App_Session/` (using military time).
*   **In-App Playback:** The app UI features a horizontal scrollable list of recorded clips (numbered 1, 2, 3... ordered latest first) seamlessly under the voice button. You can tap any specific clip to immediately play back that exact command to diagnose reasoning errors natively without leaving the app. Past sessions are retained in the `Documents` folder for long-term audits.

---

## Intelligence Layer (SLM)

To avoid forcing the user to memorize rigid trigger words (e.g., "Buggy, execute forward maneuver"), we will use a **Small Language Model (SLM)** to map natural language into structured JSON payloads.

### Architecture Decisions
1.  **Execution Host:** **The Android Phone (S26 Ultra).**
    *   *Why?* The Jetson Orin Nano's memory will be highly constrained by YOLO11n + the embedding/scaffolding model from Phase 2. The S26 Ultra has massive RAM (12GB+) and a dedicated NPU. By running the SLM on the phone, we send zero-cost JSON strings over Bluetooth, keeping the Jetson's compute completely focused on vision and motor control.
2.  **Model Selection:** We will use modern, highly capable SLMs designed for edge devices.
    *   *Candidates:* **Qwen2.5 (1.5B or 3B)**, **Phi-3.5-mini**, or **Gemma 2 (2B)**. These benchmark massively higher than older models like LLaMA 1/2 and can run effortlessly on an S26 Ultra via frameworks like MLC-LLM or MediaPipe.
3.  **Methodology:** **Strict Prompt Engineering (No Fine-Tuning).**
    *   We will provide the SLM with a rigid system prompt containing a few-shot JSON example set. The SLM will act exclusively as a natural language parser.

### The Pipeline
1.  **Listen (STT):** User says *"Hey, come over here to me."*
2.  **Distill (SLM):** The S26 Ultra runs the prompt-engineered SLM, mapping the phrase to our schema.
3.  **Command:** The SLM outputs exactly: `{"command": "follow_me"}`.
4.  **Execute:** The JSON is sent via Bluetooth to the Jetson.

### The Intent Schema
The SLM will be prompted to output exactly one of these commands, or default to `UNK`:
*   `follow_me`: Triggered by *"Come here,"* *"Follow me,"* *"Track me."*
*   `stop`: Triggered by *"Stop,"* *"Halt,"* *"Wait there."*
*   `return_to_base`: Triggered by *"Go home,"* *"Return to start."*
*   `manual_override_\{dir\}`: Translating manual commands like *"Turn left,"* *"Go forward a bit."*
*   `UNK` (Unknown): If the SLM cannot confidently map the audio (e.g., *"What's the weather?"*), it outputs `UNK`. The Buggy ignores it.
