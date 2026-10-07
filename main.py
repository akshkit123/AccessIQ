from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import base64
import numpy as np
import cv2
from deepface import DeepFace
import os
import io

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def base64_to_image(base64_string):
    # Remove the data URL prefix if present
    if 'base64,' in base64_string:
        base64_string = base64_string.split('base64,')[1]
    
    img_data = base64.b64decode(base64_string)
    nparr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

@app.post("/verify")
async def verify(data: dict):
    try:
        if 'img1' not in data or 'img2' not in data:
            raise HTTPException(status_code=400, detail="Both img1 and img2 are required")
        
        img1 = base64_to_image(data['img1'])
        img2 = base64_to_image(data['img2'])
        
        result = DeepFace.verify(
            img1_path=img1,
            img2_path=img2,
            model_name=data.get('model_name', 'VGG-Face'),
            detector_backend=data.get('detector_backend', 'opencv'),
            distance_metric=data.get('distance_metric', 'cosine'),
            enforce_detection=True
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="192.168.209.62", port=5000)