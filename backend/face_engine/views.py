import logging
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import verify_facial_images

logger = logging.getLogger('accessiq.face_engine')


class FaceVerifyAPIView(APIView):
    """
    Facial verification endpoint using DeepFace + OpenCV fallback.
    Supports both REST format and backward-compatibility with legacy /verify endpoint.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        img1 = data.get('img1')
        img2 = data.get('img2')

        if not img1 or not img2:
            return Response({
                'error': 'Both img1 and img2 base64 strings are required',
                'verified': False,
                'isVerified': False,
            }, status=status.HTTP_400_BAD_REQUEST)

        model_name = data.get('model_name')
        detector_backend = data.get('detector_backend')
        distance_metric = data.get('distance_metric')

        try:
            result = verify_facial_images(
                img1_data=img1,
                img2_data=img2,
                model_name=model_name,
                detector_backend=detector_backend,
                distance_metric=distance_metric
            )

            # Add isVerified alias for React Native FaceVerification.tsx compatibility
            result['isVerified'] = result.get('verified', False)
            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Facial verification error: {str(e)}")
            return Response({
                'error': str(e),
                'verified': False,
                'isVerified': False,
            }, status=status.HTTP_400_BAD_REQUEST)
