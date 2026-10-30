"""Face check for webcam snapshots (OpenCV Haar cascade).
If OpenCV is not installed, `analyze_frame` reports available=False and the exam carries on
without the face check, so the rest of the app still works."""
try:
    import cv2
    import numpy as np
    _cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    AVAILABLE = not _cascade.empty()
except Exception:  # pragma: no cover
    AVAILABLE = False


def analyze_frame(image_bytes):
    """Returns {'available': bool, 'faces': int}."""
    if not AVAILABLE:
        return {'available': False, 'faces': 0}
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {'available': True, 'faces': 0}
        gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
        return {'available': True, 'faces': int(len(faces))}
    except Exception:
        return {'available': False, 'faces': 0}


def detect_face(image_bytes):
    return analyze_frame(image_bytes)['faces'] >= 1
