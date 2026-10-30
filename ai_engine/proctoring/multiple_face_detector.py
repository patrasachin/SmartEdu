from .face_detector import analyze_frame


def detect_multiple_faces(image_bytes):
    return analyze_frame(image_bytes)['faces'] > 1
