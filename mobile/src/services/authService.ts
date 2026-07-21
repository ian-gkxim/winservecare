/**
 * Authentication service for the WinServeCare Carer Mobile App.
 *
 * Handles:
 * - Login with identifier/password
 * - Token refresh (silent refresh when within 5 min of expiry)
 * - Logout (clears tokens and resets state)
 * - Device token registration for push notifications
 * - Lockout after 5 consecutive failed login attempts (60s cooldown)
 *
 * Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7
 */

import * as SecureStore from 'expo-secure-store';

import apiClient, { storeTokens, logout as clearStoredTokens } from './apiClient';
import { LoginRequest, TokenResponse, DeviceTokenRequest } from '@/types';

// --- Constants ---

const TOKEN_EXPIRY_KEY = 'token_expiry_at';
const MAX_FAILED_ATTEMPTS = 5;
const LOCKOUT_DURATION_MS = 60_000; // 60 seconds
const SILENT_REFRESH_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes before expiry
const LOGIN_TIMEOUT_MS = 15_000; // 15 seconds

// --- State ---

let failedAttempts = 0;
let lockoutUntil: number | null = null;
let refreshTimerId: ReturnType<typeof setTimeout> | null = null;

// --- Error Types ---

export interface AuthError {
  type: 'invalid_credentials' | 'lockout' | 'timeout' | 'offline' | 'unknown';
  message: string;
  lockoutRemainingMs?: number;
}

// --- Public API ---

/**
 * Check whether the login is currently locked out.
 * Returns the remaining lockout time in ms, or 0 if not locked out.
 */
export function getLockoutRemainingMs(): number {
  if (lockoutUntil === null) return 0;
  const remaining = lockoutUntil - Date.now();
  if (remaining <= 0) {
    lockoutUntil = null;
    return 0;
  }
  return remaining;
}

/**
 * Whether login is currently locked out.
 */
export function isLockedOut(): boolean {
  return getLockoutRemainingMs() > 0;
}

/**
 * Attempt to log in with the given credentials.
 * Enforces lockout after 5 consecutive failures.
 * Times out after 15 seconds.
 */
export async function login(
  identifier: string,
  password: string
): Promise<TokenResponse | AuthError> {
  // Check lockout
  const lockoutRemaining = getLockoutRemainingMs();
  if (lockoutRemaining > 0) {
    return {
      type: 'lockout',
      message: `Too many failed attempts. Please wait before trying again.`,
      lockoutRemainingMs: lockoutRemaining,
    };
  }

  try {
    const payload: LoginRequest = { identifier, password };

    const response = await apiClient.post<TokenResponse>(
      '/api/mobile/auth/login',
      payload,
      { timeout: LOGIN_TIMEOUT_MS }
    );

    const tokenResponse = response.data;

    // Store tokens securely
    await storeTokens(tokenResponse);

    // Store expiry time for silent refresh scheduling
    const expiresAtMs = Date.now() + tokenResponse.expires_in * 1000;
    await SecureStore.setItemAsync(TOKEN_EXPIRY_KEY, String(expiresAtMs));

    // Reset failed attempts on success
    failedAttempts = 0;
    lockoutUntil = null;

    // Schedule silent refresh
    scheduleTokenRefresh(tokenResponse.expires_in);

    return tokenResponse;
  } catch (error: any) {
    // Handle timeout
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return {
        type: 'timeout',
        message: 'Connection timed out. Please check your network and try again.',
      };
    }

    // Handle network errors (offline)
    if (!error.response) {
      return {
        type: 'offline',
        message: 'No network connection. Please check your connectivity and try again.',
      };
    }

    // Handle 401 / invalid credentials
    if (error.response?.status === 401) {
      failedAttempts += 1;

      if (failedAttempts >= MAX_FAILED_ATTEMPTS) {
        lockoutUntil = Date.now() + LOCKOUT_DURATION_MS;
        return {
          type: 'lockout',
          message: `Too many failed attempts. Login disabled for 60 seconds.`,
          lockoutRemainingMs: LOCKOUT_DURATION_MS,
        };
      }

      return {
        type: 'invalid_credentials',
        message: 'Incorrect identifier or password. Please try again.',
      };
    }

    // Other errors
    return {
      type: 'unknown',
      message: 'An unexpected error occurred. Please try again.',
    };
  }
}

/**
 * Attempt a silent token refresh.
 * Returns the new token response, or null if refresh failed.
 */
export async function refresh(): Promise<TokenResponse | null> {
  try {
    const response = await apiClient.post<TokenResponse>(
      '/api/mobile/auth/refresh'
    );

    const tokenResponse = response.data;

    // Store new tokens
    await storeTokens(tokenResponse);

    // Update expiry
    const expiresAtMs = Date.now() + tokenResponse.expires_in * 1000;
    await SecureStore.setItemAsync(TOKEN_EXPIRY_KEY, String(expiresAtMs));

    // Schedule next refresh
    scheduleTokenRefresh(tokenResponse.expires_in);

    return tokenResponse;
  } catch {
    // Refresh failed — session expired callback handled by apiClient interceptor
    return null;
  }
}

/**
 * Log out: clear tokens, cancel scheduled refresh, stop periodic timer, and reset state.
 */
export async function logout(): Promise<void> {
  cancelScheduledRefresh();
  stopSilentRefreshTimer();
  await clearStoredTokens();
  await SecureStore.deleteItemAsync(TOKEN_EXPIRY_KEY);
  failedAttempts = 0;
  lockoutUntil = null;
}

/**
 * Register a device token for push notifications.
 */
export async function registerDeviceToken(
  token: string,
  platform: 'ios' | 'android'
): Promise<void> {
  const payload: DeviceTokenRequest = { device_token: token, platform };
  await apiClient.post('/api/mobile/auth/device-token', payload);
}

/**
 * Check if a valid (non-expired) access token exists in secure store.
 */
export async function isAuthenticated(): Promise<boolean> {
  const expiryStr = await SecureStore.getItemAsync(TOKEN_EXPIRY_KEY);
  if (!expiryStr) return false;

  const expiresAtMs = parseInt(expiryStr, 10);
  if (isNaN(expiresAtMs)) return false;

  return Date.now() < expiresAtMs;
}

/**
 * Decode the JWT access token to get the `exp` claim (seconds since epoch).
 * Returns null if no token is stored or the token cannot be decoded.
 */
export async function getTokenExpiry(): Promise<number | null> {
  const expiryStr = await SecureStore.getItemAsync(TOKEN_EXPIRY_KEY);
  if (!expiryStr) return null;

  const expiresAtMs = parseInt(expiryStr, 10);
  if (isNaN(expiresAtMs)) return null;

  // Return as seconds (exp claim format)
  return Math.floor(expiresAtMs / 1000);
}

/**
 * Set up silent token refresh. Checks if token is within 5 minutes of expiry
 * and schedules a refresh timer accordingly.
 * Alias for setupTokenRefresh — call on app startup when user is authenticated.
 */
export async function setupSilentRefresh(): Promise<void> {
  await setupTokenRefresh();
}

/**
 * Set up token refresh scheduling based on current token expiry.
 * Should be called on app startup if the user is already authenticated.
 */
export async function setupTokenRefresh(): Promise<void> {
  const expiryStr = await SecureStore.getItemAsync(TOKEN_EXPIRY_KEY);
  if (!expiryStr) return;

  const expiresAtMs = parseInt(expiryStr, 10);
  if (isNaN(expiresAtMs)) return;

  const remainingMs = expiresAtMs - Date.now();
  if (remainingMs <= 0) {
    // Token already expired, attempt refresh immediately
    await refresh();
    return;
  }

  const refreshInMs = Math.max(remainingMs - SILENT_REFRESH_THRESHOLD_MS, 0);
  scheduleRefreshTimer(refreshInMs);
}

// --- Silent Refresh Periodic Timer ---

const SILENT_REFRESH_INTERVAL_MS = 60_000; // Check every 60 seconds
let silentRefreshIntervalId: ReturnType<typeof setInterval> | null = null;

/**
 * Start a periodic silent refresh timer that checks token expiry every 60 seconds.
 * If the token is within 5 minutes of expiry, it triggers a refresh.
 * Call this on app startup when the user is authenticated.
 */
export function startSilentRefreshTimer(): void {
  stopSilentRefreshTimer();

  silentRefreshIntervalId = setInterval(async () => {
    const expiryStr = await SecureStore.getItemAsync(TOKEN_EXPIRY_KEY);
    if (!expiryStr) return;

    const expiresAtMs = parseInt(expiryStr, 10);
    if (isNaN(expiresAtMs)) return;

    const remainingMs = expiresAtMs - Date.now();

    if (remainingMs <= 0) {
      // Token already expired, attempt refresh
      await refresh();
    } else if (remainingMs <= SILENT_REFRESH_THRESHOLD_MS) {
      // Within 5 minutes of expiry, refresh now
      await refresh();
    }
  }, SILENT_REFRESH_INTERVAL_MS);
}

/**
 * Stop the periodic silent refresh timer.
 */
export function stopSilentRefreshTimer(): void {
  if (silentRefreshIntervalId !== null) {
    clearInterval(silentRefreshIntervalId);
    silentRefreshIntervalId = null;
  }
}

// --- Internal Helpers ---

/**
 * Schedule a silent refresh to fire `expiresInSeconds - 5min` from now.
 */
function scheduleTokenRefresh(expiresInSeconds: number): void {
  const refreshInMs = Math.max(
    expiresInSeconds * 1000 - SILENT_REFRESH_THRESHOLD_MS,
    0
  );
  scheduleRefreshTimer(refreshInMs);
}

function scheduleRefreshTimer(delayMs: number): void {
  cancelScheduledRefresh();
  refreshTimerId = setTimeout(async () => {
    await refresh();
  }, delayMs);
}

function cancelScheduledRefresh(): void {
  if (refreshTimerId !== null) {
    clearTimeout(refreshTimerId);
    refreshTimerId = null;
  }
}

// --- Testing Helpers (exported for unit tests) ---

export function _resetState(): void {
  failedAttempts = 0;
  lockoutUntil = null;
  cancelScheduledRefresh();
  stopSilentRefreshTimer();
}

export function _getFailedAttempts(): number {
  return failedAttempts;
}
