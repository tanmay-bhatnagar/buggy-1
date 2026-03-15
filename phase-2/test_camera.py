import cv2
import sys

def main():
    print("Initializing camera test...")
    # 0 is usually the default for a USB webcam like Logitech. 
    # If the Jetson has other v4l2 capture devices, this might need to be 1 or 2.
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        print("Tip: On a Jetson, your USB camera might be on a different index if other video devices exist.")
        print("You can list available devices with 'ls /dev/video*' in your Jetson terminal and change 'VideoCapture(0)' accordingly.")
        sys.exit(1)

    print("Camera initialized successfully!")
    print("A window should pop up showing the video feed.")
    print("Press 'X' or 'x' in the video window to exit.")

    while True:
        # Read a frame from the camera
        ret, frame = cap.read()

        if not ret:
            print("Error: Failed to grab a frame. Camera stream might have ended unexpectedly.")
            break

        # Display the frame
        cv2.imshow('Logitech Camera Test', frame)

        # Wait for a key event for 1 millisecond
        key = cv2.waitKey(1) & 0xFF

        # Check if the pressed key is 'X' or 'x'
        if key == ord('x') or key == ord('X'):
            print("Exiting...")
            break

    # Clean up resources
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
