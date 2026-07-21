/**
 * Login screen for the WinServeCare Carer Mobile App.
 *
 * Features:
 * - Identifier and password input fields
 * - Error message display (incorrect credentials, timeout, offline)
 * - Lockout countdown display after 5 consecutive failures
 * - Offline banner when no network connectivity
 * - 15-second timeout on login requests
 * - Retains entered identifier on failure
 * - Navigates to ScheduleScreen on success
 *
 * Requirements: 1.1, 1.2, 1.5, 1.6, 1.7
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import * as Network from 'expo-network';

import {
  login,
  isLockedOut,
  getLockoutRemainingMs,
  AuthError,
} from '../services/authService';

interface LoginScreenProps {
  onLoginSuccess: () => void;
}

export default function LoginScreen({ onLoginSuccess }: LoginScreenProps) {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);
  const [lockoutCountdown, setLockoutCountdown] = useState(0);

  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Network connectivity monitoring ---
  useEffect(() => {
    let isMounted = true;

    const checkNetwork = async () => {
      try {
        const networkState = await Network.getNetworkStateAsync();
        if (isMounted) {
          setIsOffline(!(networkState.isConnected && networkState.isInternetReachable));
        }
      } catch {
        // If network check fails, assume online to not block login
      }
    };

    // Check immediately
    checkNetwork();

    // Poll connectivity every 5 seconds
    const intervalId = setInterval(checkNetwork, 5000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  // --- Lockout countdown timer ---
  useEffect(() => {
    if (lockoutCountdown <= 0) {
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
      return;
    }

    countdownTimerRef.current = setInterval(() => {
      const remaining = getLockoutRemainingMs();
      if (remaining <= 0) {
        setLockoutCountdown(0);
        setErrorMessage(null);
      } else {
        setLockoutCountdown(Math.ceil(remaining / 1000));
      }
    }, 1000);

    return () => {
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
    };
  }, [lockoutCountdown > 0]);

  // --- Login handler ---
  const handleLogin = useCallback(async () => {
    if (!identifier.trim() || !password.trim()) {
      setErrorMessage('Please enter both identifier and password.');
      return;
    }

    if (isLockedOut()) {
      const remaining = Math.ceil(getLockoutRemainingMs() / 1000);
      setLockoutCountdown(remaining);
      setErrorMessage(`Login disabled. Try again in ${remaining} seconds.`);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    const result = await login(identifier.trim(), password);

    setIsLoading(false);

    if ('access_token' in result) {
      // Login success — navigate to main app
      setPassword('');
      onLoginSuccess();
    } else {
      // Login failed — show error, retain identifier
      const authError = result as AuthError;
      setErrorMessage(authError.message);
      setPassword('');

      if (authError.type === 'lockout' && authError.lockoutRemainingMs) {
        setLockoutCountdown(Math.ceil(authError.lockoutRemainingMs / 1000));
      }
    }
  }, [identifier, password, onLoginSuccess]);

  const isLoginDisabled = isLoading || isLockedOut() || lockoutCountdown > 0;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Offline Banner */}
        {isOffline && (
          <View style={styles.offlineBanner} accessibilityRole="alert">
            <Text style={styles.offlineBannerText}>
              No network connection. Login requires connectivity.
            </Text>
          </View>
        )}

        <View style={styles.formContainer}>
          {/* App Title */}
          <Text style={styles.title}>WinServeCare</Text>
          <Text style={styles.subtitle}>Carer Login</Text>

          {/* Error Message */}
          {errorMessage && (
            <View style={styles.errorContainer} accessibilityRole="alert">
              <Text style={styles.errorText}>{errorMessage}</Text>
            </View>
          )}

          {/* Lockout Countdown */}
          {lockoutCountdown > 0 && (
            <View style={styles.lockoutContainer} accessibilityRole="timer">
              <Text style={styles.lockoutText}>
                Login available in {lockoutCountdown}s
              </Text>
            </View>
          )}

          {/* Identifier Input */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Identifier</Text>
            <TextInput
              style={styles.input}
              value={identifier}
              onChangeText={setIdentifier}
              placeholder="Enter your identifier"
              autoCapitalize="none"
              autoCorrect={false}
              editable={!isLoading}
              accessibilityLabel="Identifier"
              testID="identifier-input"
            />
          </View>

          {/* Password Input */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="Enter your password"
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              editable={!isLoading}
              accessibilityLabel="Password"
              testID="password-input"
            />
          </View>

          {/* Login Button */}
          <TouchableOpacity
            style={[
              styles.loginButton,
              isLoginDisabled && styles.loginButtonDisabled,
            ]}
            onPress={handleLogin}
            disabled={isLoginDisabled}
            accessibilityRole="button"
            accessibilityLabel={
              lockoutCountdown > 0
                ? `Login disabled, available in ${lockoutCountdown} seconds`
                : 'Login'
            }
            accessibilityState={{ disabled: isLoginDisabled }}
            testID="login-button"
          >
            {isLoading ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <Text style={styles.loginButtonText}>
                {lockoutCountdown > 0 ? `Locked (${lockoutCountdown}s)` : 'Login'}
              </Text>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  offlineBanner: {
    backgroundColor: '#ff6b35',
    paddingVertical: 10,
    paddingHorizontal: 16,
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 10,
  },
  offlineBannerText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
  formContainer: {
    paddingHorizontal: 32,
    paddingVertical: 40,
    alignItems: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1a1a2e',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    marginBottom: 32,
  },
  errorContainer: {
    backgroundColor: '#fdecea',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
    width: '100%',
  },
  errorText: {
    color: '#d32f2f',
    fontSize: 14,
    textAlign: 'center',
  },
  lockoutContainer: {
    backgroundColor: '#fff3e0',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
    width: '100%',
  },
  lockoutText: {
    color: '#e65100',
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
  inputContainer: {
    width: '100%',
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: '#333',
  },
  loginButton: {
    backgroundColor: '#1a73e8',
    borderRadius: 8,
    paddingVertical: 14,
    paddingHorizontal: 32,
    width: '100%',
    alignItems: 'center',
    marginTop: 8,
  },
  loginButtonDisabled: {
    backgroundColor: '#94b8e8',
  },
  loginButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
