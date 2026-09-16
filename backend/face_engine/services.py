import base64
import os
import io
import sys
import logging
import numpy as np
import cv2
from django.conf import settings
from PIL import Image

# Ensure standard output can handle Unicode emojis from deepface logger on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

logger = logging.getLogger('accessiq.face_engine')


def base64_to_cv2(base64_string: str) -> np.ndarray:
    """
    Decodes a base64 string (with or without data URI scheme) to an OpenCV BGR image.
    """
    if not base64_string:
        raise ValueError("Empty base64 image data provided")

    if 'base64,' in base64_string:
        base64_string = base64_string.split('base64,')[1]

    img_data = base64.b64decode(base64_string)
    nparr = np.frombuffer(img_data, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Failed to decode image from buffer")
    return image


def cv2_to_base64(image: np.ndarray, format_ext: str = '.jpg') -> str:
    """
    Encodes an OpenCV image to a base64 JPEG string.
    """
    success, buffer = cv2.imencode(format_ext, image)
    if not success:
        raise ValueError("Failed to encode image to buffer")
    return base64.b64encode(buffer).decode('utf-8')


def file_to_cv2(file_path_or_file) -> np.ndarray:
    """
    Reads an image from a filesystem path, file-like object, or Django FieldFile into OpenCV BGR.
    """
    if hasattr(file_path_or_file, 'path') and os.path.exists(file_path_or_file.path):
        return cv2.imread(file_path_or_file.path)
    elif hasattr(file_path_or_file, 'read'):
        content = file_path_or_file.read()
        nparr = np.frombuffer(content, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif isinstance(file_path_or_file, str) and os.path.exists(file_path_or_file):
        return cv2.imread(file_path_or_file)
    else:
        raise ValueError("Invalid file path or object provided for image loading")


def detect_face_opencv(image: np.ndarray):
    """
    Detects face bounding box using OpenCV Haar cascades if available,
    or falls back to center-of-frame extraction.
    """
    if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
            if len(faces) > 0:
                return faces
        except Exception:
            pass

    # Safe fallback box covering center 60% of frame
    h, w = image.shape[:2]
    return [[int(w * 0.2), int(h * 0.2), int(w * 0.6), int(h * 0.6)]]


def opencv_fallback_similarity(img1: np.ndarray, img2: np.ndarray) -> dict:
    """
    Robust security-first fallback comparison if DeepFace encounters an unexpected failure.
    Never falsely authenticates different individuals based on simple color histograms.
    """
    logger.warning("DeepFace execution failed; falling back to strict security fail-closed stance.")
    return {
        'verified': False,
        'distance': 1.0,
        'threshold': 0.45,
        'similarity_score': 0.0,
        'confidence': 0.0,
        'model': 'FailSafe-Biometrics-Fallback',
        'detector_backend': 'fail_closed',
        'similarity_metric': 'deep_neural_network_required',
        'error': 'Biometric facial neural network could not confirm match. Access denied for campus security.',
    }


def resize_image_for_engine(image: np.ndarray, max_dim: int = 640) -> np.ndarray:
    """
    Downscales ultra-high resolution images (e.g. 4000x3000 phone camera)
    to a standard dimension for rapid inference without accuracy loss.
    """
    if image is None:
        return image
    h, w = image.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return image


YUNET_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'face_detection_yunet_2023mar.onnx')
SFACE_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'face_recognition_sface_2021dec.onnx')

_yunet_detector = None
_sface_recognizer = None


def get_yunet_and_sface():
    """
    Initializes and caches OpenCV YuNet face detector and SFace deep feature extractor.
    Runs entirely through native OpenCV DNN engine (fast, robust, SAC-compliant).
    """
    global _yunet_detector, _sface_recognizer
    if _yunet_detector is None and os.path.exists(YUNET_MODEL_PATH):
        try:
            _yunet_detector = cv2.FaceDetectorYN.create(YUNET_MODEL_PATH, '', (320, 320), score_threshold=0.45)
        except Exception as e:
            logger.warning(f"Could not initialize YuNet: {e}")
    if _sface_recognizer is None and os.path.exists(SFACE_MODEL_PATH):
        try:
            _sface_recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL_PATH, '')
        except Exception as e:
            logger.warning(f"Could not initialize SFace: {e}")
    return _yunet_detector, _sface_recognizer


def extract_sface_embedding(img_bgr: np.ndarray, detector, recognizer):
    """
    Detects face box and 5 landmarks with YuNet, aligns face, and extracts 128D SFace feature vector.
    """
    h, w = img_bgr.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(img_bgr)
    if faces is None or len(faces) == 0:
        return None, False
    aligned = recognizer.alignCrop(img_bgr, faces[0])
    feature = recognizer.feature(aligned)
    return feature, True


def verify_facial_images(img1_data, img2_data, model_name=None, detector_backend=None, distance_metric=None) -> dict:
    """
    Core face verification service.
    Accepts: base64 string, file path, Django FieldFile, or numpy array.
    Uses OpenCV YuNet + SFace Deep Neural Network with DeepFace/OpenCV fallbacks.
    """
    model_name = model_name or getattr(settings, 'DEEPFACE_MODEL', 'VGG-Face')
    detector_backend = detector_backend or getattr(settings, 'DEEPFACE_BACKEND', 'retinaface')
    if detector_backend == 'opencv' and not hasattr(cv2, 'CascadeClassifier'):
        detector_backend = 'retinaface'
    distance_metric = distance_metric or getattr(settings, 'DEEPFACE_METRIC', 'cosine')

    # Convert img1 to OpenCV ndarray
    if isinstance(img1_data, np.ndarray):
        img1 = img1_data
    elif isinstance(img1_data, str) and (';base64,' in img1_data or len(img1_data) > 300):
        img1 = base64_to_cv2(img1_data)
    else:
        img1 = file_to_cv2(img1_data)

    # Convert img2 to OpenCV ndarray
    if isinstance(img2_data, np.ndarray):
        img2 = img2_data
    elif isinstance(img2_data, str) and (';base64,' in img2_data or len(img2_data) > 300):
        img2 = base64_to_cv2(img2_data)
    else:
        img2 = file_to_cv2(img2_data)

    # Check if both images were successfully decoded
    if img1 is None or img2 is None:
        return {
            'verified': False,
            'distance': 1.0,
            'threshold': 0.363,
            'similarity_score': 0.0,
            'confidence': 0.0,
            'model': 'OpenCV-SFace-DNN',
            'detector_backend': 'YuNet-ONNX',
            'similarity_metric': 'cosine',
            'error': 'One or both facial images could not be loaded or decoded',
        }

    # Downscale for rapid real-time inference
    img1_scaled = resize_image_for_engine(img1, 640)
    img2_scaled = resize_image_for_engine(img2, 640)

    # Fast-path: Identical byte comparison
    if img1.shape == img2.shape and np.array_equal(img1, img2):
        return {
            'verified': True,
            'distance': 0.0,
            'threshold': 0.363,
            'similarity_score': 1.0,
            'confidence': 100.0,
            'model': 'Instant-Identical-Match',
            'detector_backend': 'fast_path',
            'similarity_metric': 'direct_biometric_equal',
            'error': None,
        }

    # PRIMARY ENGINE: OpenCV YuNet + SFace Deep Neural Network
    detector, recognizer = get_yunet_and_sface()
    if detector is not None and recognizer is not None:
        try:
            # Check live camera image (img2) first for face presence
            feat2, has_live_face = extract_sface_embedding(img2_scaled, detector, recognizer)
            if not has_live_face:
                return {
                    'verified': False,
                    'distance': 1.0,
                    'threshold': 0.363,
                    'similarity_score': 0.0,
                    'confidence': 0.0,
                    'model': 'OpenCV-SFace-DNN',
                    'detector_backend': 'YuNet-ONNX',
                    'similarity_metric': 'cosine',
                    'error': 'No face detected in live camera frame. Please look directly into the camera.',
                }

            # Check enrolled cardholder photo (img1) for face presence
            feat1, has_ref_face = extract_sface_embedding(img1_scaled, detector, recognizer)
            if not has_ref_face:
                return {
                    'verified': False,
                    'distance': 1.0,
                    'threshold': 0.363,
                    'similarity_score': 0.0,
                    'confidence': 0.0,
                    'model': 'OpenCV-SFace-DNN',
                    'detector_backend': 'YuNet-ONNX',
                    'similarity_metric': 'cosine',
                    'error': 'No face detected in registered cardholder photo.',
                }

            # Compute Cosine Similarity between 128D embeddings
            cosine_sim = float(recognizer.match(feat1, feat2, cv2.FaceRecognizerSF_FR_COSINE))
            threshold = 0.363  # Official OpenCV SFace cosine distance threshold
            verified = bool(cosine_sim >= threshold)
            distance = round(max(0.0, 1.0 - cosine_sim), 4)
            similarity_score = round(max(0.0, min(1.0, cosine_sim)), 4)
            confidence = round(max(0.0, min(100.0, cosine_sim * 100.0)), 1)
            err = None if verified else 'Facial biometrics do not match registered cardholder profile.'

            return {
                'verified': verified,
                'distance': distance,
                'threshold': threshold,
                'similarity_score': similarity_score,
                'confidence': confidence,
                'model': 'OpenCV-SFace-DNN',
                'detector_backend': 'YuNet-ONNX',
                'similarity_metric': 'cosine',
                'error': err,
            }

        except Exception as ex:
            logger.warning(f"SFace execution encountered an exception: {ex}")

    # SECONDARY ENGINE: DeepFace fallback
    try:
        from deepface import DeepFace

        result = DeepFace.verify(
            img1_path=img1_scaled,
            img2_path=img2_scaled,
            model_name=model_name,
            detector_backend=detector_backend,
            distance_metric=distance_metric,
            enforce_detection=True
        )

        distance = float(result.get('distance', 1.0))
        threshold = getattr(settings, 'FACIAL_RECOGNITION_THRESHOLD', 0.42)
        verified = bool(distance <= threshold)
        similarity_score = max(0.0, min(1.0, 1.0 - (distance / max(threshold * 2, 0.01))))

        return {
            'verified': verified,
            'distance': round(distance, 4),
            'threshold': round(threshold, 4),
            'similarity_score': round(similarity_score, 4),
            'confidence': round(similarity_score * 100, 1),
            'model': model_name,
            'detector_backend': detector_backend,
            'similarity_metric': distance_metric,
            'error': None if verified else 'Facial biometrics do not match registered cardholder profile.',
        }

    except Exception as e:
        err_str = str(e)
        logger.warning(f"Face verification exception: {err_str}")
        if any(kw in err_str.lower() for kw in ['face could not be detected', 'processing img', 'no face']):
            return {
                'verified': False,
                'distance': 1.0,
                'threshold': 0.42,
                'similarity_score': 0.0,
                'confidence': 0.0,
                'model': model_name,
                'detector_backend': detector_backend,
                'similarity_metric': distance_metric,
                'error': 'No face detected in live camera frame. Please look directly into the camera.',
            }

        fallback_res = opencv_fallback_similarity(img1_scaled, img2_scaled)
        if fallback_res.get('error'):
            fallback_res['error'] = f"Face detection note: {err_str}"
        return fallback_res

