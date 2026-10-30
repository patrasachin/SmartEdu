from ai_engine.proctoring.face_detector import analyze_frame


def check_face_present(image_bytes):
    return analyze_frame(image_bytes)['faces'] >= 1


def check_multiple_faces(image_bytes):
    return analyze_frame(image_bytes)['faces'] > 1
