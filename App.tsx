import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Image,
  Alert,
  ActivityIndicator,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  Platform,
  Modal,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Device from 'expo-device';
import { StatusBar } from 'expo-status-bar';
import * as Animatable from 'react-native-animatable';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import FaceVerification from './FaceVerification';

// Default development backend server address
const DEFAULT_API_BASE_URL = 'http://192.168.0.104:8000';

export default function AccessIQMobileApp() {
  // Navigation & Tabs
  const [activeTab, setActiveTab] = useState<'verify' | 'enroll' | 'logs' | 'alerts' | 'settings'>('verify');
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [customServerIp, setCustomServerIp] = useState('');

  // Device registration state (Authorized Device Management)
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [imei, setImei] = useState('');
  const [pin, setPin] = useState('');
  const [isRegistered, setIsRegistered] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showLogin, setShowLogin] = useState(false);

  // Student / Identity Verification state
  const [cardNumber, setCardNumber] = useState('MITWPU20261234');
  const [selectedLocation, setSelectedLocation] = useState('LAB-AIML');
  const [studentData, setStudentData] = useState<any>(null);
  const [isVerified, setIsVerified] = useState<boolean | null>(null);
  const [verificationResultData, setVerificationResultData] = useState<any>(null);
  const [error, setError] = useState('');
  const [showFaceVerification, setShowFaceVerification] = useState(false);

  // Barcode Camera Scanner state
  const [showBarcodeScanner, setShowBarcodeScanner] = useState(false);
  const [scannerMode, setScannerMode] = useState<'verify' | 'enroll'>('verify');
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();

  // Mobile Student Enrollment state
  const [enrollBarcode, setEnrollBarcode] = useState('');
  const [enrollName, setEnrollName] = useState('');
  const [enrollStudentId, setEnrollStudentId] = useState('');
  const [enrollDepartment, setEnrollDepartment] = useState('School of Computer Science & Engineering');
  const [enrollCourse, setEnrollCourse] = useState('B.Tech AI & Data Science');
  const [enrollYear, setEnrollYear] = useState('3');
  const [enrollPhotoBase64, setEnrollPhotoBase64] = useState<string | null>(null);
  const [enrollPhotoUri, setEnrollPhotoUri] = useState<string | null>(null);
  const [isEnrolling, setIsEnrolling] = useState(false);
  const [enrollmentResult, setEnrollmentResult] = useState<any>(null);

  // Logs & Alerts state
  const [recentLogs, setRecentLogs] = useState<any[]>([]);
  const [activeAlerts, setActiveAlerts] = useState<any[]>([]);

  const logger = (type: string, message: string, data: any = {}) => {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${type}] ${message}`, data);
  };

  useEffect(() => {
    initApp();
  }, []);

  const initApp = async () => {
    try {
      const storedUrl = await AsyncStorage.getItem('accessiq_api_url');
      if (storedUrl) {
        setApiBaseUrl(storedUrl);
        setCustomServerIp(storedUrl);
      }
      await checkRegistrationStatus();
    } catch (e) {
      console.warn('Initialization error:', e);
      setIsLoading(false);
    }
  };

  const checkRegistrationStatus = async () => {
    try {
      const [storedImei, storedPin] = await AsyncStorage.multiGet(['imei', 'pin']);
      logger('STORAGE', 'Checking stored device credentials', { storedImei, storedPin });

      if (storedImei[1] && storedPin[1]) {
        setImei(storedImei[1]);
        setPin(storedPin[1]);
        setIsRegistered(true);
        setShowLogin(false);
        logger('DEVICE', 'Authorized device recognized');
      } else {
        const deviceId = Device.osInternalBuildId || `TERMINAL-${Math.floor(1000 + Math.random() * 9000)}`;
        setImei(deviceId);
        setShowLogin(true);
        logger('DEVICE', 'Device not registered yet');
      }
    } catch (error) {
      logger('ERROR', 'Failed to read registration state', { error });
      setShowLogin(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeviceRegister = async () => {
    if (!username || !password) {
      Alert.alert('Required', 'Please enter your username and security credentials');
      return;
    }

    setIsLoading(true);
    const requestBody = {
      Username: username,
      Password: password,
      IdentificationNo: imei,
      PhoneName: Device.modelName || 'Mobile Scanner Client',
      OS: Device.osName || 'Android',
      Verson: Device.osVersion || '1.0',
    };

    try {
      const url = `${apiBaseUrl}/api/auth/devices/register/`;
      logger('API', 'Registering authorized device with backend', { url });

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (data.MessageStatus || response.status === 200 || response.status === 201) {
        const devicePin = String(data.MessageCode || data.device?.pin || '9421');
        await AsyncStorage.multiSet([
          ['pin', devicePin],
          ['imei', imei],
        ]);
        setPin(devicePin);
        setIsRegistered(true);
        setShowLogin(false);
        Alert.alert('Device Authorized', `Terminal enrolled successfully.\nAssigned Security PIN: ${devicePin}`);
      } else {
        Alert.alert('Registration Failed', data.Message || data.error || 'Server rejected registration');
      }
    } catch (err: any) {
      Alert.alert('Connection Failed', `Could not connect to backend at ${apiBaseUrl}.\nPlease check server IP in Settings.`);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchIdentityDetails = async (codeToVerify?: string) => {
    const targetCode = (codeToVerify || cardNumber).trim();
    if (!targetCode) {
      Alert.alert('Missing ID', 'Please scan or type a barcode ID number');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const url = `${apiBaseUrl}/api/barcode/verify/`;
      logger('API', 'Verifying barcode identity', { url, targetCode });

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ barcode: targetCode }),
      });

      const data = await response.json();
      if (response.ok && (data.success || data.MessageStatus)) {
        setStudentData(data);
        setIsVerified(null);
        setVerificationResultData(null);
      } else {
        Alert.alert('Identity Not Found', data.Message || data.error || 'No matching campus cardholder record found');
        setError(data.Message || 'Unregistered barcode ID');
      }
    } catch (err: any) {
      Alert.alert('Network Error', `Could not reach ${apiBaseUrl}.\nEnsure the Django backend is running.`);
      setError('Connection failed to backend');
    } finally {
      setIsLoading(false);
    }
  };

  const startBarcodeScan = async () => {
    try {
      if (!cameraPermission?.granted) {
        const perm = await requestCameraPermission();
        if (!perm || !perm.granted) {
          Alert.alert('Camera Permission', 'Camera permission is required to scan ID card barcodes.');
          return;
        }
      }
      setScannerMode('verify');
      setShowBarcodeScanner(true);
    } catch (e: any) {
      Alert.alert('Camera Error', 'Unable to start camera for barcode scanning: ' + (e?.message || 'Permission denied'));
    }
  };

  const startEnrollBarcodeScan = async () => {
    try {
      if (!cameraPermission?.granted) {
        const perm = await requestCameraPermission();
        if (!perm || !perm.granted) {
          Alert.alert('Camera Permission', 'Camera permission is required to scan ID card barcodes.');
          return;
        }
      }
      setScannerMode('enroll');
      setShowBarcodeScanner(true);
    } catch (e: any) {
      Alert.alert('Camera Error', 'Unable to start camera for barcode scanning: ' + (e?.message || 'Permission denied'));
    }
  };

  const handleBarcodeScanned = (scanEvent: any) => {
    const rawData = scanEvent?.data || scanEvent?.raw || scanEvent;
    if (!rawData) return;
    const scannedCode = String(rawData).trim();
    if (!scannedCode) return;

    setShowBarcodeScanner(false);

    if (scannerMode === 'enroll') {
      setEnrollBarcode(scannedCode);
      if (!enrollStudentId) {
        setEnrollStudentId(scannedCode);
      }
      Alert.alert('Card Scanned', `Scanned Barcode: ${scannedCode}\nAttached to enrollment form.`);
    } else {
      setCardNumber(scannedCode);
      setTimeout(() => {
        fetchIdentityDetails(scannedCode);
      }, 250);
    }
  };

  const takeEnrollPhoto = async () => {
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Camera permission is required to capture cardholder facial photo.');
        return;
      }
      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      });

      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        setEnrollPhotoUri(asset.uri);
        if (asset.base64) {
          setEnrollPhotoBase64(`data:image/jpeg;base64,${asset.base64}`);
        }
      }
    } catch (e: any) {
      Alert.alert('Camera Error', 'Could not capture photo: ' + (e?.message || 'Unknown error'));
    }
  };

  const pickEnrollPhoto = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      });

      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        setEnrollPhotoUri(asset.uri);
        if (asset.base64) {
          setEnrollPhotoBase64(`data:image/jpeg;base64,${asset.base64}`);
        }
      }
    } catch (e: any) {
      Alert.alert('Gallery Error', 'Could not select photo: ' + (e?.message || 'Unknown error'));
    }
  };

  const handleEnrollSubmit = async () => {
    if (!enrollName.trim()) {
      Alert.alert('Required Field', 'Please enter student full name');
      return;
    }
    if (!enrollBarcode.trim()) {
      Alert.alert('Required Field', 'Please scan or type a barcode identifier');
      return;
    }
    if (!enrollPhotoBase64) {
      Alert.alert('Required Field', 'Please capture or upload a face photo for biometric verification');
      return;
    }

    setIsEnrolling(true);
    try {
      const cleanB64 = enrollPhotoBase64.includes('base64,')
        ? enrollPhotoBase64.split('base64,')[1]
        : enrollPhotoBase64;

      const payload = {
        name: enrollName.trim(),
        student_id: (enrollStudentId || enrollBarcode).trim(),
        barcode: enrollBarcode.trim(),
        department: enrollDepartment.trim(),
        course: enrollCourse.trim(),
        year_of_study: parseInt(enrollYear, 10) || 1,
        photo_base64: cleanB64,
      };

      const url = `${apiBaseUrl}/api/identity/students/enroll/`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (response.ok && data.success) {
        setEnrollmentResult(data);
        Alert.alert(
          'Enrolled Successfully',
          `Student "${data.data?.name || enrollName}" has been enrolled with barcode ID "${data.data?.barcode || enrollBarcode}".`
        );
      } else {
        Alert.alert('Enrollment Failed', data.error || data.detail || 'Server could not process enrollment');
      }
    } catch (err: any) {
      Alert.alert('Network Error', `Could not reach ${apiBaseUrl}.\nPlease verify backend is running.`);
    } finally {
      setIsEnrolling(false);
    }
  };

  const resetEnrollForm = () => {
    setEnrollBarcode('');
    setEnrollName('');
    setEnrollStudentId('');
    setEnrollPhotoBase64(null);
    setEnrollPhotoUri(null);
    setEnrollmentResult(null);
  };

  const handleFaceVerificationComplete = (verificationResponse: any) => {
    setShowFaceVerification(false);
    if (verificationResponse.isVerified) {
      setIsVerified(true);
      setError('');
      setVerificationResultData(verificationResponse.result);
      Alert.alert('ACCESS GRANTED', '✅ Dual-Factor Verification Successful!\nFace biometrics & location permissions verified.');
    } else {
      setIsVerified(false);
      const reason = verificationResponse.error || "Faces don't match cardholder template";
      setError(reason);
      Alert.alert('ACCESS DENIED', `❌ Authentication Failed:\n${reason}`);
    }
  };

  const fetchLogs = async () => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/access/logs/`);
      const data = await resp.json();
      if (Array.isArray(data)) {
        setRecentLogs(data);
      }
    } catch (e) {
      console.warn('Failed to load logs', e);
    }
  };

  const fetchAlerts = async () => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/security/alerts/`);
      const data = await resp.json();
      if (Array.isArray(data)) {
        setActiveAlerts(data);
      }
    } catch (e) {
      console.warn('Failed to load alerts', e);
    }
  };

  const handleSaveServerConfig = async () => {
    if (!customServerIp.trim()) return;
    const cleanUrl = customServerIp.trim().replace(/\/+$/, '');
    await AsyncStorage.setItem('accessiq_api_url', cleanUrl);
    setApiBaseUrl(cleanUrl);
    Alert.alert('Saved', `API Base URL updated to:\n${cleanUrl}`);
  };

  const resetScanner = () => {
    setStudentData(null);
    setIsVerified(null);
    setVerificationResultData(null);
    setError('');
    setShowFaceVerification(false);
  };

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#38bdf8" />
        <Text style={styles.loadingText}>AccessIQ Initializing...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.appTitle}>🛡️ AccessIQ</Text>
          <Text style={styles.appSubtitle}>Smart Campus Identity & Access</Text>
        </View>
        <View style={styles.deviceBadge}>
          <Text style={styles.deviceBadgeText}>PIN: {pin || 'AUTH'}</Text>
        </View>
      </View>

      {/* Tab Navigation */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'verify' && styles.activeTabButton]}
          onPress={() => setActiveTab('verify')}
        >
          <Text style={[styles.tabButtonText, activeTab === 'verify' && styles.activeTabButtonText]}>
            🔍 Verify
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'enroll' && styles.activeTabButton]}
          onPress={() => setActiveTab('enroll')}
        >
          <Text style={[styles.tabButtonText, activeTab === 'enroll' && styles.activeTabButtonText]}>
            ➕ Enroll
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'logs' && styles.activeTabButton]}
          onPress={() => {
            setActiveTab('logs');
            fetchLogs();
          }}
        >
          <Text style={[styles.tabButtonText, activeTab === 'logs' && styles.activeTabButtonText]}>
            📋 Logs
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'alerts' && styles.activeTabButton]}
          onPress={() => {
            setActiveTab('alerts');
            fetchAlerts();
          }}
        >
          <Text style={[styles.tabButtonText, activeTab === 'alerts' && styles.activeTabButtonText]}>
            ⚠️ Alerts
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'settings' && styles.activeTabButton]}
          onPress={() => setActiveTab('settings')}
        >
          <Text style={[styles.tabButtonText, activeTab === 'settings' && styles.activeTabButtonText]}>
            ⚙️ Server
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Device Registration Screen */}
        {showLogin ? (
          <Animatable.View animation="slideInUp" duration={600} style={styles.cardContainer}>
            <Text style={styles.cardTitle}>Authorize Terminal Device</Text>
            <Text style={styles.cardSubtitle}>
              Register this handheld verification device with the AccessIQ security console
            </Text>

            <Text style={styles.label}>Operator Username:</Text>
            <TextInput
              style={styles.input}
              value={username}
              onChangeText={setUsername}
              placeholder="e.g. security_staff or admin"
              placeholderTextColor="#64748b"
            />

            <Text style={styles.label}>Operator Password:</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="Enter password"
              placeholderTextColor="#64748b"
              secureTextEntry
            />

            <View style={styles.deviceInfoBox}>
              <Text style={styles.deviceInfoText}>Device Identifier: {imei}</Text>
              <Text style={styles.deviceInfoText}>Target Host: {apiBaseUrl}</Text>
            </View>

            <TouchableOpacity style={styles.primaryButton} onPress={handleDeviceRegister}>
              <Text style={styles.primaryButtonText}>Register Terminal</Text>
            </TouchableOpacity>
          </Animatable.View>
        ) : activeTab === 'verify' ? (
          /* Core Dual-Factor Verification Tab */
          <Animatable.View animation="fadeIn" duration={400} style={styles.cardContainer}>
            <Text style={styles.cardTitle}>Campus Access Gate</Text>
            <Text style={styles.cardSubtitle}>Dual-Factor: Barcode Identification + Facial Biometrics</Text>

            {/* Location Selector Chips */}
            <Text style={styles.label}>Select Secured Location:</Text>
            <View style={styles.chipRow}>
              {[
                { code: 'LAB-AIML', name: 'AI Lab' },
                { code: 'LAB-COMP1', name: 'CS Lab 1' },
                { code: 'LIB-MAIN', name: 'Library' },
                { code: 'ROOM-SRV', name: 'Server Rm' },
              ].map((loc) => (
                <TouchableOpacity
                  key={loc.code}
                  style={[styles.chip, selectedLocation === loc.code && styles.chipActive]}
                  onPress={() => setSelectedLocation(loc.code)}
                >
                  <Text style={[styles.chipText, selectedLocation === loc.code && styles.chipTextActive]}>
                    {loc.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {studentData ? (
              /* Identified Cardholder Preview */
              <Animatable.View animation="zoomIn" duration={500} style={styles.idCard}>
                <View style={styles.idCardHeader}>
                  {studentData.photo_url || studentData.Photo ? (
                    <Image
                      source={{
                        uri: studentData.photo_url
                          ? `${apiBaseUrl}${studentData.photo_url}`
                          : `data:image/jpeg;base64,${studentData.Photo}`,
                      }}
                      style={styles.idPhoto}
                    />
                  ) : (
                    <View style={[styles.idPhoto, styles.noPhoto]}>
                      <Text style={styles.noPhotoText}>👤</Text>
                    </View>
                  )}
                  <View style={styles.idDetails}>
                    <Text style={styles.idName}>{studentData.name || studentData.StudentName}</Text>
                    <Text style={styles.idCode}>ID: {studentData.id || studentData.EnrollmentNo}</Text>
                    <Text style={styles.idDept}>{studentData.department}</Text>
                    <Text style={styles.idStatus}>
                      Status: {studentData.Status || studentData.CurrentStatus || 'Active'}
                    </Text>
                  </View>
                </View>

                {/* Face Verification Modal / Component */}
                {!showFaceVerification && isVerified === null && (
                  <TouchableOpacity
                    style={[styles.primaryButton, { marginTop: 14 }]}
                    onPress={() => setShowFaceVerification(true)}
                  >
                    <Text style={styles.primaryButtonText}>📸 Start Live Face Verification</Text>
                  </TouchableOpacity>
                )}

                {showFaceVerification && (
                  <FaceVerification
                    storedPhoto={studentData.Photo}
                    barcode={cardNumber}
                    locationCode={selectedLocation}
                    apiBaseUrl={apiBaseUrl}
                    onVerificationComplete={handleFaceVerificationComplete}
                    onCancel={() => setShowFaceVerification(false)}
                  />
                )}

                {/* Verification Decision Card */}
                {isVerified !== null && (
                  <Animatable.View
                    animation={isVerified ? 'tada' : 'shake'}
                    duration={800}
                    style={[
                      styles.decisionBox,
                      isVerified ? styles.decisionGranted : styles.decisionDenied,
                    ]}
                  >
                    <Text style={styles.decisionTitle}>
                      {isVerified ? '✅ ACCESS GRANTED' : '❌ ACCESS DENIED'}
                    </Text>
                    <Text style={styles.decisionSubtitle}>
                      {isVerified
                        ? `Authorized for ${selectedLocation}`
                        : error || 'Verification failed. Security alert logged.'}
                    </Text>
                    {verificationResultData?.similarity_score !== undefined && (
                      <Text style={styles.decisionMetric}>
                        Biometric Confidence: {Math.round(verificationResultData.similarity_score * 100)}%
                      </Text>
                    )}
                  </Animatable.View>
                )}

                <TouchableOpacity style={styles.secondaryButton} onPress={resetScanner}>
                  <Text style={styles.secondaryButtonText}>Scan Another Card</Text>
                </TouchableOpacity>
              </Animatable.View>
            ) : (
              /* Barcode / QR ID Input Form */
              <View>
                <TouchableOpacity style={styles.cameraScanButton} onPress={startBarcodeScan}>
                  <Text style={styles.cameraScanButtonText}>📷 Scan Barcode with Camera</Text>
                </TouchableOpacity>

                <View style={styles.dividerRow}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>OR ENTER / PRESET</Text>
                  <View style={styles.dividerLine} />
                </View>

                <Text style={styles.label}>Barcode / QR Identifier:</Text>
                <TextInput
                  style={styles.input}
                  value={cardNumber}
                  onChangeText={setCardNumber}
                  placeholder="Scan or enter ID (e.g. MITWPU20261234)"
                  placeholderTextColor="#64748b"
                />

                <View style={styles.demoCodesContainer}>
                  <Text style={styles.demoLabel}>Demo Presets:</Text>
                  <View style={styles.demoRow}>
                    <TouchableOpacity
                      style={styles.demoPill}
                      onPress={() => setCardNumber('MITWPU20261234')}
                    >
                      <Text style={styles.demoPillText}>Hetvi (Student)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.demoPill}
                      onPress={() => setCardNumber('STAFF-202601')}
                    >
                      <Text style={styles.demoPillText}>Dr. Rajesh (Staff)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.demoPill}
                      onPress={() => setCardNumber('INVALID-999')}
                    >
                      <Text style={styles.demoPillText}>Invalid ID</Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {error ? <Text style={styles.errorText}>⚠️ {error}</Text> : null}

                <TouchableOpacity style={styles.primaryButton} onPress={() => fetchIdentityDetails()}>
                  <Text style={styles.primaryButtonText}>🔍 Verify Barcode & Retrieve User</Text>
                </TouchableOpacity>
              </View>
            )}
          </Animatable.View>
        ) : activeTab === 'enroll' ? (
          /* Mobile Student Enrollment Screen */
          <Animatable.View animation="fadeIn" duration={400} style={styles.cardContainer}>
            <Text style={styles.cardTitle}>Mobile Student Enrollment</Text>
            <Text style={styles.cardSubtitle}>Scan physical card barcode & capture live facial photo</Text>

            {enrollmentResult ? (
              /* Success Card */
              <Animatable.View animation="zoomIn" duration={500} style={styles.enrollSuccessCard}>
                <View style={styles.enrollSuccessBadge}>
                  <Text style={styles.enrollSuccessBadgeText}>🎉 ENROLLMENT CONFIRMED</Text>
                </View>

                <View style={styles.idCardHeader}>
                  {enrollPhotoUri ? (
                    <Image source={{ uri: enrollPhotoUri }} style={styles.idPhoto} />
                  ) : (
                    <View style={[styles.idPhoto, styles.noPhoto]}>
                      <Text style={styles.noPhotoText}>👤</Text>
                    </View>
                  )}
                  <View style={styles.idDetails}>
                    <Text style={styles.idName}>{enrollmentResult.data?.name || enrollName}</Text>
                    <Text style={styles.idCode}>Barcode: {enrollmentResult.data?.barcode || enrollBarcode}</Text>
                    <Text style={styles.idDept}>{enrollmentResult.data?.department || enrollDepartment}</Text>
                    <Text style={styles.idStatus}>Access: Campus Wide (Active)</Text>
                  </View>
                </View>

                <TouchableOpacity
                  style={[styles.primaryButton, { marginTop: 16 }]}
                  onPress={() => {
                    const enrolledCode = enrollmentResult.data?.barcode || enrollBarcode;
                    resetEnrollForm();
                    setCardNumber(enrolledCode);
                    setActiveTab('verify');
                    setTimeout(() => {
                      fetchIdentityDetails(enrolledCode);
                    }, 300);
                  }}
                >
                  <Text style={styles.primaryButtonText}>🔍 Test Gate Verification Now</Text>
                </TouchableOpacity>

                <TouchableOpacity style={styles.secondaryButton} onPress={resetEnrollForm}>
                  <Text style={styles.secondaryButtonText}>➕ Enroll Another Student Card</Text>
                </TouchableOpacity>
              </Animatable.View>
            ) : (
              /* Enrollment Form */
              <View>
                {/* Step 1: Barcode Scan */}
                <TouchableOpacity style={styles.cameraScanButton} onPress={startEnrollBarcodeScan}>
                  <Text style={styles.cameraScanButtonText}>📷 Scan Barcode on Card with Phone</Text>
                </TouchableOpacity>

                <Text style={styles.label}>Scanned Barcode / QR ID *</Text>
                <TextInput
                  style={styles.input}
                  value={enrollBarcode}
                  onChangeText={(val) => {
                    setEnrollBarcode(val);
                    if (!enrollStudentId) setEnrollStudentId(val);
                  }}
                  placeholder="e.g. MITWPU20269999"
                  placeholderTextColor="#64748b"
                />

                {/* Step 2: Cardholder Details */}
                <Text style={styles.label}>Full Name *</Text>
                <TextInput
                  style={styles.input}
                  value={enrollName}
                  onChangeText={setEnrollName}
                  placeholder="e.g. Priya Deshmukh"
                  placeholderTextColor="#64748b"
                />

                <Text style={styles.label}>Student Roll No / Institutional ID</Text>
                <TextInput
                  style={styles.input}
                  value={enrollStudentId}
                  onChangeText={setEnrollStudentId}
                  placeholder="e.g. MITWPU20269999"
                  placeholderTextColor="#64748b"
                />

                <Text style={styles.label}>Department</Text>
                <TextInput
                  style={styles.input}
                  value={enrollDepartment}
                  onChangeText={setEnrollDepartment}
                  placeholder="Department"
                  placeholderTextColor="#64748b"
                />

                <Text style={styles.label}>Course / Program</Text>
                <TextInput
                  style={styles.input}
                  value={enrollCourse}
                  onChangeText={setEnrollCourse}
                  placeholder="Course"
                  placeholderTextColor="#64748b"
                />

                {/* Step 3: Biometric Face Photo */}
                <Text style={styles.label}>Cardholder Facial Photo *</Text>
                {enrollPhotoUri ? (
                  <View style={styles.photoPreviewContainer}>
                    <Image source={{ uri: enrollPhotoUri }} style={styles.photoPreview} />
                    <View style={styles.photoPreviewInfo}>
                      <Text style={styles.photoPreviewTitle}>Biometric Template Ready</Text>
                      <Text style={styles.photoPreviewSubtitle}>Face image captured for AI DeepFace comparison</Text>
                    </View>
                  </View>
                ) : null}

                <View style={styles.photoButtonsRow}>
                  <TouchableOpacity style={styles.photoActionBtn} onPress={takeEnrollPhoto}>
                    <Text style={styles.photoActionBtnText}>📸 Take Live Photo</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.photoActionBtn, styles.photoActionBtnSecondary]} onPress={pickEnrollPhoto}>
                    <Text style={styles.photoActionBtnTextSecondary}>🖼️ Gallery</Text>
                  </TouchableOpacity>
                </View>

                {/* Step 4: Submit Enrollment */}
                <TouchableOpacity
                  style={[styles.primaryButton, { marginTop: 18 }]}
                  onPress={handleEnrollSubmit}
                  disabled={isEnrolling}
                >
                  {isEnrolling ? (
                    <ActivityIndicator color="#ffffff" />
                  ) : (
                    <Text style={styles.primaryButtonText}>✅ Complete Student Enrollment</Text>
                  )}
                </TouchableOpacity>
              </View>
            )}
          </Animatable.View>
        ) : activeTab === 'logs' ? (
          /* Access Logs Tab */
          <View style={styles.cardContainer}>
            <Text style={styles.cardTitle}>Recent Access Logs</Text>
            <Text style={styles.cardSubtitle}>Real-time campus perimeter audit trail</Text>

            {recentLogs.map((log, idx) => (
              <View key={log.id || idx} style={styles.logItem}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.logName}>{log.user_name || log.scanned_barcode}</Text>
                  <Text style={styles.logDetail}>
                    {log.location_code || 'GATE'} • {log.direction || 'ENTRY'}
                  </Text>
                  <Text style={styles.logTime}>{log.timestamp}</Text>
                </View>
                <View
                  style={[
                    styles.statusPill,
                    log.final_decision === 'GRANTED' ? styles.pillGreen : styles.pillRed,
                  ]}
                >
                  <Text
                    style={[
                      styles.statusPillText,
                      log.final_decision === 'GRANTED' ? styles.pillTextGreen : styles.pillTextRed,
                    ]}
                  >
                    {log.final_decision}
                  </Text>
                </View>
              </View>
            ))}

            {recentLogs.length === 0 && (
              <Text style={styles.emptyText}>No recent access logs loaded yet.</Text>
            )}

            <TouchableOpacity style={styles.secondaryButton} onPress={fetchLogs}>
              <Text style={styles.secondaryButtonText}>🔄 Refresh Logs</Text>
            </TouchableOpacity>
          </View>
        ) : activeTab === 'alerts' ? (
          /* Security Alerts Tab */
          <View style={styles.cardContainer}>
            <Text style={styles.cardTitle}>Security Incident Alerts</Text>
            <Text style={styles.cardSubtitle}>Active threats, face mismatches, and breach alerts</Text>

            {activeAlerts.map((alert, idx) => (
              <View key={alert.id || idx} style={styles.alertItem}>
                <View style={styles.alertHeaderRow}>
                  <Text style={styles.alertType}>{alert.alert_type_display || alert.alert_type}</Text>
                  <Text style={styles.alertSeverity}>{alert.severity}</Text>
                </View>
                <Text style={styles.alertDesc}>{alert.description}</Text>
                <Text style={styles.alertMeta}>
                  {alert.location_name || 'Perimeter'} • {alert.timestamp}
                </Text>
              </View>
            ))}

            {activeAlerts.length === 0 && (
              <Text style={styles.emptyText}>No active security alerts recorded.</Text>
            )}

            <TouchableOpacity style={styles.secondaryButton} onPress={fetchAlerts}>
              <Text style={styles.secondaryButtonText}>🔄 Refresh Alerts</Text>
            </TouchableOpacity>
          </View>
        ) : (
          /* Settings / Server Config Tab */
          <View style={styles.cardContainer}>
            <Text style={styles.cardTitle}>Backend Server Configuration</Text>
            <Text style={styles.cardSubtitle}>Configure Django REST Framework API Endpoint</Text>

            <Text style={styles.label}>Server Base URL:</Text>
            <TextInput
              style={styles.input}
              value={customServerIp}
              onChangeText={setCustomServerIp}
              placeholder="e.g. http://192.168.1.100:8000"
              placeholderTextColor="#64748b"
            />

            <View style={styles.deviceInfoBox}>
              <Text style={styles.deviceInfoText}>Current URL: {apiBaseUrl}</Text>
              <Text style={styles.deviceInfoText}>Terminal IMEI: {imei}</Text>
              <Text style={styles.deviceInfoText}>PIN: {pin || 'None'}</Text>
            </View>

            <TouchableOpacity style={styles.primaryButton} onPress={handleSaveServerConfig}>
              <Text style={styles.primaryButtonText}>Save Server Configuration</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      {/* Modal: Camera Barcode Scanner Viewfinder */}
      <Modal
        visible={showBarcodeScanner}
        animationType="slide"
        onRequestClose={() => setShowBarcodeScanner(false)}
      >
        <SafeAreaView style={styles.cameraModalContainer}>
          <View style={styles.cameraModalHeader}>
            <View>
              <Text style={styles.cameraModalTitle}>
                {scannerMode === 'enroll' ? 'Scan New Card Barcode' : 'Scan ID Card Barcode'}
              </Text>
              <Text style={styles.cameraModalSubtitle}>
                {scannerMode === 'enroll'
                  ? 'Align student card barcode to link with profile'
                  : 'Hold camera steady over printed barcode or QR'}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.cameraCloseButton}
              onPress={() => setShowBarcodeScanner(false)}
            >
              <Text style={styles.cameraCloseButtonText}>✕ Cancel</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.cameraViewport}>
            <CameraView
              style={StyleSheet.absoluteFillObject}
              facing="back"
              barcodeScannerSettings={{
                barcodeTypes: ['qr', 'code128', 'code39', 'ean13', 'ean8', 'upc_a', 'upc_e', 'pdf417'],
              }}
              onBarcodeScanned={handleBarcodeScanned}
            />

            {/* Target Reticle Overlay */}
            <View style={styles.overlayContainer}>
              <View style={styles.scanTargetBox}>
                <View style={styles.scanLaser} />
              </View>
              <Text style={styles.scanInstructionText}>
                Align student card barcode inside box
              </Text>
            </View>
          </View>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0a0f1d',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
    backgroundColor: '#111827',
  },
  appTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#38bdf8',
    letterSpacing: 0.5,
  },
  appSubtitle: {
    fontSize: 12,
    color: '#94a3b8',
  },
  deviceBadge: {
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    borderWidth: 1,
    borderColor: '#38bdf8',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  deviceBadgeText: {
    color: '#38bdf8',
    fontWeight: '700',
    fontSize: 12,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#111827',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
    gap: 8,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 8,
  },
  activeTabButton: {
    backgroundColor: 'rgba(56, 189, 248, 0.18)',
  },
  tabButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748b',
  },
  activeTabButtonText: {
    color: '#38bdf8',
  },
  scrollContent: {
    padding: 16,
  },
  cardContainer: {
    backgroundColor: '#111827',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#1e293b',
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#f8fafc',
    marginBottom: 4,
  },
  cardSubtitle: {
    fontSize: 13,
    color: '#94a3b8',
    marginBottom: 16,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#cbd5e1',
    marginBottom: 6,
    marginTop: 8,
  },
  input: {
    backgroundColor: '#1e293b',
    borderColor: '#334155',
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#f8fafc',
    fontSize: 15,
    marginBottom: 12,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 14,
  },
  chip: {
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  chipActive: {
    borderColor: '#38bdf8',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
  },
  chipText: {
    color: '#94a3b8',
    fontSize: 12,
    fontWeight: '500',
  },
  chipTextActive: {
    color: '#38bdf8',
    fontWeight: '700',
  },
  primaryButton: {
    backgroundColor: '#0284c7',
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginVertical: 8,
  },
  primaryButtonText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '700',
  },
  secondaryButton: {
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  secondaryButtonText: {
    color: '#cbd5e1',
    fontSize: 14,
    fontWeight: '600',
  },
  deviceInfoBox: {
    backgroundColor: '#1e293b',
    padding: 12,
    borderRadius: 8,
    marginVertical: 10,
  },
  deviceInfoText: {
    color: '#94a3b8',
    fontSize: 12,
    marginVertical: 2,
  },
  idCard: {
    backgroundColor: '#1e293b',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155',
    marginVertical: 10,
  },
  idCardHeader: {
    flexDirection: 'row',
    gap: 14,
    alignItems: 'center',
  },
  idPhoto: {
    width: 70,
    height: 70,
    borderRadius: 35,
    borderWidth: 2,
    borderColor: '#38bdf8',
  },
  noPhoto: {
    backgroundColor: '#334155',
    justifyContent: 'center',
    alignItems: 'center',
  },
  noPhotoText: {
    fontSize: 32,
  },
  idDetails: {
    flex: 1,
  },
  idName: {
    fontSize: 18,
    fontWeight: '700',
    color: '#f8fafc',
  },
  idCode: {
    fontSize: 13,
    color: '#38bdf8',
    fontWeight: '600',
  },
  idDept: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 2,
  },
  idStatus: {
    fontSize: 11,
    color: '#4ade80',
    fontWeight: '600',
    marginTop: 2,
  },
  decisionBox: {
    borderRadius: 12,
    padding: 14,
    marginTop: 14,
    alignItems: 'center',
    borderWidth: 1.5,
  },
  decisionGranted: {
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
    borderColor: '#22c55e',
  },
  decisionDenied: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: '#ef4444',
  },
  decisionTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#ffffff',
  },
  decisionSubtitle: {
    fontSize: 13,
    color: '#cbd5e1',
    marginTop: 4,
    textAlign: 'center',
  },
  decisionMetric: {
    fontSize: 12,
    color: '#38bdf8',
    marginTop: 6,
    fontWeight: '600',
  },
  demoCodesContainer: {
    marginBottom: 12,
  },
  demoLabel: {
    color: '#64748b',
    fontSize: 11,
    marginBottom: 4,
  },
  demoRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  demoPill: {
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  demoPillText: {
    color: '#38bdf8',
    fontSize: 11,
    fontWeight: '600',
  },
  logItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  logName: {
    color: '#f8fafc',
    fontWeight: '600',
    fontSize: 14,
  },
  logDetail: {
    color: '#94a3b8',
    fontSize: 12,
  },
  logTime: {
    color: '#64748b',
    fontSize: 10,
    marginTop: 2,
  },
  statusPill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  pillGreen: {
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
  },
  pillRed: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
  },
  statusPillText: {
    fontSize: 11,
    fontWeight: '700',
  },
  pillTextGreen: {
    color: '#4ade80',
  },
  pillTextRed: {
    color: '#f87171',
  },
  alertItem: {
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.3)',
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
  },
  alertHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  alertType: {
    color: '#f87171',
    fontWeight: '700',
    fontSize: 13,
  },
  alertSeverity: {
    backgroundColor: '#ef4444',
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '800',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  alertDesc: {
    color: '#f8fafc',
    fontSize: 12,
    marginVertical: 4,
  },
  alertMeta: {
    color: '#94a3b8',
    fontSize: 10,
  },
  emptyText: {
    color: '#64748b',
    textAlign: 'center',
    paddingVertical: 20,
    fontSize: 13,
  },
  errorText: {
    color: '#f87171',
    fontSize: 12,
    marginVertical: 6,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0a0f1d',
  },
  loadingText: {
    color: '#38bdf8',
    marginTop: 12,
    fontSize: 14,
    fontWeight: '600',
  },
  cameraScanButton: {
    backgroundColor: '#0284c7',
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'center',
    shadowColor: '#0284c7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 4,
  },
  cameraScanButtonText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 15,
  },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 10,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#334155',
  },
  dividerText: {
    color: '#64748b',
    fontSize: 11,
    fontWeight: '600',
    paddingHorizontal: 10,
  },
  cameraModalContainer: {
    flex: 1,
    backgroundColor: '#0a0f1d',
  },
  cameraModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#111827',
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  cameraModalTitle: {
    color: '#f8fafc',
    fontSize: 16,
    fontWeight: '700',
  },
  cameraModalSubtitle: {
    color: '#94a3b8',
    fontSize: 11,
    marginTop: 2,
  },
  cameraCloseButton: {
    backgroundColor: '#ef4444',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  cameraCloseButtonText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 12,
  },
  cameraViewport: {
    flex: 1,
    position: 'relative',
    backgroundColor: '#000000',
  },
  overlayContainer: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.45)',
  },
  scanTargetBox: {
    width: 280,
    height: 160,
    borderWidth: 2,
    borderColor: '#38bdf8',
    borderRadius: 12,
    backgroundColor: 'transparent',
    overflow: 'hidden',
    justifyContent: 'center',
  },
  scanLaser: {
    width: '100%',
    height: 2,
    backgroundColor: '#ef4444',
    shadowColor: '#ef4444',
    shadowOpacity: 0.9,
    shadowRadius: 5,
  },
  scanInstructionText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '600',
    marginTop: 18,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
  },
  photoPreviewContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    borderRadius: 10,
    padding: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#38bdf8',
    gap: 12,
  },
  photoPreview: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 2,
    borderColor: '#38bdf8',
  },
  photoPreviewInfo: {
    flex: 1,
  },
  photoPreviewTitle: {
    color: '#38bdf8',
    fontWeight: '700',
    fontSize: 13,
  },
  photoPreviewSubtitle: {
    color: '#94a3b8',
    fontSize: 11,
    marginTop: 2,
  },
  photoButtonsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 10,
  },
  photoActionBtn: {
    flex: 1,
    backgroundColor: '#0284c7',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  photoActionBtnSecondary: {
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
  },
  photoActionBtnText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
  },
  photoActionBtnTextSecondary: {
    color: '#cbd5e1',
    fontSize: 13,
    fontWeight: '600',
  },
  enrollSuccessCard: {
    backgroundColor: '#1e293b',
    borderRadius: 14,
    padding: 18,
    borderWidth: 1.5,
    borderColor: '#22c55e',
    marginVertical: 10,
  },
  enrollSuccessBadge: {
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#22c55e',
  },
  enrollSuccessBadgeText: {
    color: '#4ade80',
    fontWeight: '800',
    fontSize: 12,
  },
});
