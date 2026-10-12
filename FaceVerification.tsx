import React, { useState } from 'react';
import {
  ScrollView,
  View,
  Text,
  Alert,
  TouchableOpacity,
  Image,
  StyleSheet,
  ActivityIndicator
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as Animatable from 'react-native-animatable';
import axios from 'axios';

export type FaceComparisonResult = {
  verified: boolean;
  distance: number;
  threshold: number;
  similarity_score?: number;
  model: string;
  detector_backend: string;
  similarity_metric: string;
};

export type VerificationResponse = {
  isVerified: boolean;
  error?: string;
  result?: FaceComparisonResult;
  capturedBase64?: string;
};

interface FaceVerificationProps {
  storedPhoto?: string;
  barcode?: string;
  locationCode?: string;
  apiBaseUrl: string;
  onVerificationComplete: (result: VerificationResponse) => void;
  onCancel: () => void;
}

const FaceVerification: React.FC<FaceVerificationProps> = ({
  storedPhoto,
  barcode,
  locationCode = 'LAB-AIML',
  apiBaseUrl,
  onVerificationComplete,
  onCancel,
}) => {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [capturedBase64, setCapturedBase64] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const takePhoto = async () => {
    setError(null);

    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission Denied', 'Camera access is required for live facial verification.');
      return;
    }

    try {
      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false,
        quality: 0.7,
        base64: true,
      });

      if (!result.canceled && result.assets?.[0]?.uri) {
        const asset = result.assets[0];
        setImageUri(asset.uri);
        const b64 = asset.base64 ? `data:image/jpeg;base64,${asset.base64}` : null;
        setCapturedBase64(b64);

        if (asset.base64) {
          await verifyCapturedFace(asset.base64);
        }
      }
    } catch (err: any) {
      console.error('Camera capture error:', err);
      setError('Camera error: ' + (err.message || 'Failed to capture photo'));
    }
  };

  const verifyCapturedFace = async (liveB64: string) => {
    try {
      setProcessing(true);
      setError(null);

      const cleanCaptured = liveB64.includes('base64,') ? liveB64.split('base64,')[1] : liveB64;

      // If we have barcode & locationCode, run the complete AccessIQ Dual-Authentication endpoint
      if (barcode) {
        const dualUrl = `${apiBaseUrl}/api/access/verify/`;
        try {
          const resp = await axios.post(
            dualUrl,
            {
              barcode: barcode,
              live_face: cleanCaptured,
              location_code: locationCode,
              direction: 'ENTRY',
            },
            {
              headers: { 'Content-Type': 'application/json' },
              timeout: 45000,
            }
          );

          const isMatch = resp.data.face_verified || resp.data.decision === 'GRANTED';
          onVerificationComplete({
            isVerified: isMatch,
            result: {
              verified: isMatch,
              distance: resp.data.face_distance ?? 0.2,
              threshold: 0.40,
              similarity_score: resp.data.face_similarity ?? 0.85,
              model: 'DeepFace-VGG',
              detector_backend: 'opencv',
              similarity_metric: 'cosine',
            },
            capturedBase64: cleanCaptured,
          });
          return;
        } catch (dualErr: any) {
          // If dual-authentication returned 403 (access denied), check if it was face mismatch or permission
          if (dualErr.response && dualErr.response.data) {
            const dData = dualErr.response.data;
            onVerificationComplete({
              isVerified: Boolean(dData.face_verified),
              error: dData.failure_reason || 'Dual-factor verification denied',
              result: {
                verified: Boolean(dData.face_verified),
                distance: dData.face_distance ?? 0.8,
                threshold: 0.40,
                similarity_score: dData.face_similarity ?? 0.2,
                model: 'DeepFace-VGG',
                detector_backend: 'opencv',
                similarity_metric: 'cosine',
              },
              capturedBase64: cleanCaptured,
            });
            return;
          }
          console.warn('Dual endpoint error, falling back to direct /verify:', dualErr.message);
        }
      }

      // Direct face comparison fallback (/api/face/verify/ or legacy /verify)
      if (!storedPhoto) {
        setError('No registered cardholder photo available to compare against.');
        setProcessing(false);
        return;
      }

      const cleanStored = storedPhoto.includes('base64,') ? storedPhoto.split('base64,')[1] : storedPhoto;
      const verifyUrl = `${apiBaseUrl}/api/face/verify/`;

      const response = await axios.post(
        verifyUrl,
        {
          img1: cleanStored,
          img2: cleanCaptured,
        },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 45000,
        }
      );

      const isVerified = Boolean(response.data.verified ?? response.data.isVerified);
      onVerificationComplete({
        isVerified: isVerified,
        result: response.data,
        capturedBase64: cleanCaptured,
      });

    } catch (err: any) {
      console.error('Face verification error:', err);
      let errMsg = 'Failed to verify face. Please ensure server is running.';
      if (err.response?.data?.error) {
        errMsg = err.response.data.error;
      } else if (err.code === 'ECONNABORTED') {
        errMsg = 'Verification request timed out.';
      }

      setError(errMsg);
      onVerificationComplete({
        isVerified: false,
        error: errMsg,
      });
    } finally {
      setProcessing(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Animatable.Text animation="fadeInDown" style={styles.title}>
        Biometric Face Verification
      </Animatable.Text>
      <Text style={styles.subtitle}>
        Align face clearly inside the frame and ensure good lighting
      </Text>

      {imageUri ? (
        <Animatable.Image
          animation="zoomIn"
          duration={600}
          source={{ uri: imageUri }}
          style={styles.imagePreview}
        />
      ) : (
        <View style={styles.placeholderBox}>
          <Text style={styles.placeholderIcon}>📸</Text>
          <Text style={styles.placeholderText}>No photo captured yet</Text>
        </View>
      )}

      {processing && (
        <Animatable.View animation="pulse" iterationCount="infinite" style={styles.loadingBox}>
          <ActivityIndicator size="large" color="#0284c7" />
          <Text style={styles.loadingText}>Running DeepFace biometrics analysis...</Text>
        </Animatable.View>
      )}

      {error ? (
        <Animatable.View animation="shake" style={styles.errorBox}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </Animatable.View>
      ) : null}

      <View style={styles.buttonGroup}>
        <TouchableOpacity
          style={[styles.button, styles.captureButton]}
          onPress={takePhoto}
          disabled={processing}
        >
          <Text style={styles.buttonText}>{imageUri ? '🔄 Retake Photo' : '📷 Take Photo'}</Text>
        </TouchableOpacity>

        {!processing && (
          <TouchableOpacity style={[styles.button, styles.cancelButton]} onPress={onCancel}>
            <Text style={styles.buttonText}>Cancel</Text>
          </TouchableOpacity>
        )}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#0f172a',
    borderRadius: 16,
    marginVertical: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#f8fafc',
    marginBottom: 6,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 13,
    color: '#94a3b8',
    marginBottom: 18,
    textAlign: 'center',
  },
  imagePreview: {
    width: 210,
    height: 210,
    borderRadius: 105,
    borderWidth: 4,
    borderColor: '#38bdf8',
    marginVertical: 14,
  },
  placeholderBox: {
    width: 200,
    height: 200,
    borderRadius: 100,
    borderWidth: 2,
    borderColor: '#334155',
    borderStyle: 'dashed',
    justifyContent: 'center',
    alignItems: 'center',
    marginVertical: 14,
    backgroundColor: '#1e293b',
  },
  placeholderIcon: {
    fontSize: 48,
    marginBottom: 8,
  },
  placeholderText: {
    color: '#64748b',
    fontSize: 13,
  },
  loadingBox: {
    marginVertical: 14,
    alignItems: 'center',
  },
  loadingText: {
    color: '#38bdf8',
    fontSize: 14,
    marginTop: 8,
    fontWeight: '500',
  },
  errorBox: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.4)',
    padding: 10,
    borderRadius: 8,
    marginVertical: 10,
    maxWidth: '90%',
  },
  errorText: {
    color: '#fca5a5',
    fontSize: 13,
    textAlign: 'center',
  },
  buttonGroup: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
  },
  button: {
    paddingVertical: 12,
    paddingHorizontal: 22,
    borderRadius: 10,
    minWidth: 125,
    alignItems: 'center',
  },
  captureButton: {
    backgroundColor: '#0284c7',
  },
  cancelButton: {
    backgroundColor: '#334155',
  },
  buttonText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '600',
  },
});

export default FaceVerification;
