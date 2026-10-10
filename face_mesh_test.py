import time

import cv2
import mediapipe as mp
import numpy as np
import pygame


mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

RIGHT_EYE = [33, 160, 158, 133, 153, 144]
LEFT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [61, 13, 14, 291]

EAR_THRESHOLD = 0.20
MAR_THRESHOLD = 0.50
DROWSY_SECONDS = 2.0
YAWN_SECONDS = 1.5

WINDOW_NAME = "AI Eye Monitoring - Face Mesh"


def calculate_ear(eye_points):
    p1, p2, p3, p4, p5, p6 = eye_points

    vertical1 = np.linalg.norm(p2 - p6)
    vertical2 = np.linalg.norm(p3 - p5)
    horizontal = np.linalg.norm(p1 - p4)

    if horizontal == 0:
        return 0.0

    return (vertical1 + vertical2) / (2.0 * horizontal)


def calculate_mar(mouth_points):
    p1, p2, p3, p4 = mouth_points

    vertical = np.linalg.norm(p2 - p3)
    horizontal = np.linalg.norm(p1 - p4)

    if horizontal == 0:
        return 0.0

    return vertical / horizontal


def get_points(face_landmarks, indices, width, height):
    return np.array([
        [
            int(face_landmarks.landmark[index].x * width),
            int(face_landmarks.landmark[index].y * height),
        ]
        for index in indices
    ])


def main():
    camera = None
    face_mesh = None
    alarm = None

    closed_start_time = None
    yawn_start_time = None

    try:
        pygame.mixer.init(
            frequency=44100,
            size=-16,
            channels=1,
        )

        sample_rate = 44100
        duration = 0.5
        t = np.linspace(
            0,
            duration,
            int(sample_rate * duration),
            endpoint=False,
        )
        sound_wave = np.sin(2 * np.pi * 1000 * t)
        sound_array = (sound_wave * 16000).astype(np.int16)
        alarm = pygame.sndarray.make_sound(sound_array)

        face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        camera = cv2.VideoCapture(0)

        if not camera.isOpened():
            print("Could not access camera")
            return

        cv2.namedWindow(WINDOW_NAME)
        print("Click the camera window, then tap Q to quit.")

        while True:
            success, frame = camera.read()

            if not success:
                print("Could not read a camera frame")
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)
            now = time.monotonic()

            if results.multi_face_landmarks:
                height, width = frame.shape[:2]
                face_landmarks = results.multi_face_landmarks[0]

                right_eye_points = get_points(
                    face_landmarks, RIGHT_EYE, width, height
                )
                left_eye_points = get_points(
                    face_landmarks, LEFT_EYE, width, height
                )
                mouth_points = get_points(
                    face_landmarks, MOUTH, width, height
                )

                right_ear = calculate_ear(right_eye_points)
                left_ear = calculate_ear(left_eye_points)
                ear = (right_ear + left_ear) / 2.0
                mar = calculate_mar(mouth_points)

                if ear < EAR_THRESHOLD:
                    eye_status = "EYES CLOSED"

                    if closed_start_time is None:
                        closed_start_time = now

                    if now - closed_start_time >= DROWSY_SECONDS:
                        eye_status = "DROWSINESS ALERT!"
                else:
                    eye_status = "EYES OPEN"
                    closed_start_time = None

                if mar > MAR_THRESHOLD:
                    if yawn_start_time is None:
                        yawn_start_time = now

                    if now - yawn_start_time >= YAWN_SECONDS:
                        yawn_status = "YAWNING DETECTED!"
                    else:
                        yawn_status = "MOUTH OPEN"
                else:
                    yawn_start_time = None
                    yawn_status = "NORMAL"

                # Shared alarm for drowsiness and yawning.
                if (
                    eye_status == "DROWSINESS ALERT!"
                    or yawn_status == "YAWNING DETECTED!"
                ):
                    if not pygame.mixer.get_busy():
                        alarm.play()
                else:
                    alarm.stop()

                cv2.putText(
                    frame,
                    f"EAR: {ear:.2f}",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    frame,
                    eye_status,
                    (30, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    frame,
                    f"MAR: {mar:.2f}",
                    (30, 130),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 0),
                    2,
                )
                cv2.putText(
                    frame,
                    yawn_status,
                    (30, 170),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2,
                )

                mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=mp_face_mesh.FACEMESH_TESSELATION,
                )

            else:
                # Prevent an old alert continuing after tracking is lost.
                closed_start_time = None
                yawn_start_time = None
                alarm.stop()

                cv2.putText(
                    frame,
                    "NO FACE DETECTED",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

            # One display and one keyboard check per frame.
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q")):
                break

    except KeyboardInterrupt:
        pass

    finally:
        # One cleanup block, also used if an error occurs.
        if alarm is not None:
            alarm.stop()

        if camera is not None:
            camera.release()

        cv2.destroyAllWindows()
        cv2.waitKey(1)  # Process pending window-close events.

        if face_mesh is not None:
            face_mesh.close()

        if pygame.mixer.get_init() is not None:
            pygame.mixer.quit()


if __name__ == "__main__":
    main()