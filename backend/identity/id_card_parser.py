import re
import cv2
import base64
import numpy as np
from PIL import Image
import io
import logging

logger = logging.getLogger('accessiq.id_card_parser')

INSTITUTION_WORDS = {
    'FACULTY', 'ENGINEERING', 'TECHNOLOGY', 'UNIVERSITY', 'COLLEGE',
    'MIT', 'WPU', 'MIT-WPU', 'SCHOOL', 'ACADEMY', 'CAMPUS', 'PUNE',
    'INDIA', 'STUDENT', 'IDENTITY', 'CARD', 'MAHARASHTRA', 'INSTITUTE',
    'OF', 'AND', 'DEPARTMENT'
}

COURSE_KEYWORDS = {
    'MCA', 'B.TECH', 'M.TECH', 'BTECH', 'MTECH', 'BBA', 'MBA',
    'BCA', 'PHD', 'B.SC', 'M.SC', 'BSC', 'MSC', 'B.E', 'M.E',
    'B.COM', 'M.COM', 'B.PHARM', 'M.PHARM'
}


def load_image_as_cv2(image_input) -> np.ndarray:
    """Converts various image input types into an OpenCV BGR numpy array."""
    if isinstance(image_input, np.ndarray):
        return image_input

    if isinstance(image_input, str):
        if image_input.startswith('data:image') or ';base64,' in image_input or len(image_input) > 500:
            raw_b64 = image_input.split('base64,')[1] if 'base64,' in image_input else image_input
            img_bytes = base64.b64decode(raw_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
        else:
            img = cv2.imread(image_input)
            if img is not None:
                return img

    if hasattr(image_input, 'read'):
        content = image_input.read()
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            return img

    if isinstance(image_input, (bytes, bytearray)):
        nparr = np.frombuffer(image_input, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            return img

    raise ValueError("Unsupported or invalid image input format")


def crop_card_photo(img: np.ndarray) -> str:
    """
    Crops student passport photo from ID card and returns base64 data URI.
    In standard campus ID cards (like MIT-WPU), the passport photo is centered
    in the upper half (approx y: 22% to 49%, x: 30% to 66%).
    """
    h, w = img.shape[:2]
    try:
        py1, py2 = int(h * 0.22), int(h * 0.49)
        px1, px2 = int(w * 0.29), int(w * 0.67)
        photo_crop = img[py1:py2, px1:px2]

        if photo_crop.size > 0:
            success, buffer = cv2.imencode('.jpg', photo_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            if success:
                b64 = base64.b64encode(buffer).decode('utf-8')
                return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        logger.warning(f"Error cropping card photo: {e}")

    return ""


def extract_barcode_from_image(img: np.ndarray) -> str:
    """Uses zxing-cpp to read 1D / 2D barcodes from ID card image."""
    try:
        import zxingcpp
        # 1. Full image scan
        results = zxingcpp.read_barcodes(img)
        if results:
            return results[0].text.strip()

        # 2. Lower barcode region crop scan (y: 55% to 80%)
        h, w = img.shape[:2]
        by1, by2 = int(h * 0.55), int(h * 0.82)
        bx1, bx2 = int(w * 0.15), int(w * 0.85)
        crop = img[by1:by2, bx1:bx2]
        if crop.size > 0:
            results = zxingcpp.read_barcodes(crop)
            if results:
                return results[0].text.strip()

            # Contrast stretch
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            results = zxingcpp.read_barcodes(gray)
            if results:
                return results[0].text.strip()
    except Exception as e:
        logger.warning(f"zxingcpp barcode detection error: {e}")

    return ""


def parse_id_card_data(image_input) -> dict:
    """
    Complete AI parsing pipeline for Student ID Cards:
    - Reads Barcode with zxing-cpp
    - Extracts text via RapidOCR
    - Auto-extracts Name, ID, Course, Department, Phone, Blood Group
    - Auto-crops student face photo
    """
    img = load_image_as_cv2(image_input)
    h, w = img.shape[:2]

    # 1. Barcode Detection
    barcode_val = extract_barcode_from_image(img)

    # 2. OCR Text Extraction via RapidOCR
    lines = []
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        ocr_res, _ = engine(img)
        if ocr_res:
            lines = [l[1].strip() for l in ocr_res if l and len(l) > 1 and l[1]]
    except Exception as e:
        logger.warning(f"RapidOCR execution warning: {e}")

    # 3. Field Parsing Logic
    student_id = barcode_val
    name = ''
    course = ''
    department = 'Faculty of Engineering and Technology'
    contact_phone = ''
    blood_group = ''

    # Scan OCR lines
    for i, line in enumerate(lines):
        # Emergency / Contact Phone
        if any(k in line.lower() for k in ['emerg', 'phone', 'mob', 'contact', 'no:']):
            nums = re.findall(r'\d{10,12}', line)
            if nums and not contact_phone:
                raw_p = nums[0]
                contact_phone = raw_p[2:] if (raw_p.startswith('91') and len(raw_p) == 12) else raw_p

        # Blood Group
        if 'blood' in line.lower() and not blood_group:
            bg_m = re.search(r'([ABOab0][+-])', line)
            if bg_m:
                blood_group = bg_m.group(1).upper()

        # Name Detection
        # Format e.g. "Nandanwar Priyesh -" or "Nandanwar Priyesh"
        cleaned = line.rstrip('-').strip()
        words = cleaned.split()
        if not name and len(words) >= 2:
            # Check if all words are alphabetic and not institutional headers
            if not any(w.upper() in INSTITUTION_WORDS for w in words) and all(w.isalpha() for w in words):
                name = cleaned
                # Look ahead for course (e.g. MCA, B.Tech)
                for j in range(i + 1, min(i + 4, len(lines))):
                    cand = lines[j].strip().upper()
                    clean_cand = re.sub(r'[^A-Z.]', '', cand)
                    if clean_cand in COURSE_KEYWORDS or any(ck in cand for ck in COURSE_KEYWORDS):
                        course = cand.split('-')[0].strip()
                        break

    # Fallback student_id from OCR digits if barcode was not detected
    if not student_id:
        for line in lines:
            cleaned_num = re.sub(r'\D', '', line)
            if len(cleaned_num) == 10 and (cleaned_num.startswith('12') or cleaned_num.startswith('10')):
                student_id = cleaned_num
                break

    # If barcode is still empty, match student_id
    if not barcode_val and student_id:
        barcode_val = student_id
    elif barcode_val and not student_id:
        student_id = barcode_val

    # Normalize Course
    if not course:
        # Default course for MIT-WPU Faculty of Engineering & Technology
        course = 'MCA'

    # Split Name into First Name & Last Name (Indian format: Surname First e.g. "Nandanwar Priyesh")
    name_parts = name.split()
    if len(name_parts) >= 2:
        last_name = name_parts[0]
        first_name = ' '.join(name_parts[1:])
    elif len(name_parts) == 1:
        first_name = name_parts[0]
        last_name = ''
    else:
        first_name = ''
        last_name = ''

    # Crop Face Photo from ID Card
    photo_b64 = crop_card_photo(img)

    return {
        'success': bool(student_id or name),
        'student_id': student_id,
        'barcode': barcode_val,
        'first_name': first_name,
        'last_name': last_name,
        'full_name': f"{first_name} {last_name}".strip() if first_name else name,
        'course': course,
        'department': department,
        'semester': 3,
        'contact_phone': contact_phone,
        'blood_group': blood_group,
        'photo_b64': photo_b64,
        'raw_lines': lines
    }
