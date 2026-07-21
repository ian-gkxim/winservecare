/**
 * Axios-based HTTP client for communicating with the WinServeCare backend.
 *
 * Features:
 * - Configurable base URL (defaults to http://localhost:8000)
 * - Automatic Bearer token injection from expo-secure-store
 * - 401 response interceptor with silent token refresh
 * - On refresh failure, clears tokens and triggers re-login callback
 *
 * Requirements: 1.3, 1.4
 */

import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';
import * as SecureStore from 'expo-secure-store';

import { TokenResponse } from '@/types';

// Secure store keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// Default configuration
const DEFAULT_BASE_URL = 'http://localhost:8000';

/**
 * Callback invoked when the session is invalid (refresh fails).
 * The consuming code should set this to trigger navigation to the login screen.
 */
let onSessionExpired: (() => void) | null = null;

/**
 * Register a callback to be invoked when the session cannot be refreshed.
 */
export function setSessionExpiredCallback(callback: () => void): void {
  onSessionExpired = callback;
}

/**
 * Flag to prevent multiple simultaneous refresh attempts.
 */
let isRefreshing = false;

/**
 * Queue of requests waiting for the token refresh to complete.
 */
let failedRequestQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

/**
 * Process the queue of failed requests after a refresh attempt.
 */
function processQueue(error: unknown, token: string | null): void {
  failedRequestQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token!);
    }
  });
  failedRequestQueue = [];
}

/**
 * Create the configured Axios instance.
 */
function createApiClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: DEFAULT_BASE_URL,
    timeout: 15000, // 15 second timeout per requirement 1.7
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // --- Request Interceptor: Inject Bearer token ---
  instance.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
      // Skip token injection for auth endpoints (login/refresh)
      const isAuthEndpoint =
        config.url?.includes('/auth/login') ||
        config.url?.includes('/auth/refresh');

      if (!isAuthEndpoint) {
        const token = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }

      return config;
    },
    (error) => Promise.reject(error)
  );

  // --- Response Interceptor: Handle 401 with token refresh ---
  instance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & {
        _retry?: boolean;
      };

      // Only intercept 401 errors that haven't already been retried
      if (error.response?.status !== 401 || originalRequest._retry) {
        return Promise.reject(error);
      }

      // Don't try to refresh if the refresh endpoint itself returned 401
      if (originalRequest.url?.includes('/auth/refresh')) {
        await clearTokens();
        onSessionExpired?.();
        return Promise.reject(error);
      }

      // If already refreshing, queue this request
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedRequestQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          originalRequest._retry = true;
          return instance(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);

        if (!refreshToken) {
          throw new Error('No refresh token available');
        }

        // Attempt token refresh
        const response = await axios.post<TokenResponse>(
          `${instance.defaults.baseURL}/api/mobile/auth/refresh`,
          { refresh_token: refreshToken },
          { headers: { 'Content-Type': 'application/json' } }
        );

        const { access_token, refresh_token } = response.data;

        // Store new tokens
        await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, access_token);
        await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refresh_token);

        // Process queued requests with new token
        processQueue(null, access_token);

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return instance(originalRequest);
      } catch (refreshError) {
        // Refresh failed — clear tokens and trigger re-login
        processQueue(refreshError, null);
        await clearTokens();
        onSessionExpired?.();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
  );

  return instance;
}

/**
 * Clear all stored authentication tokens.
 */
async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
}

/**
 * Store tokens after successful authentication.
 */
export async function storeTokens(tokenResponse: TokenResponse): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, tokenResponse.access_token);
  await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, tokenResponse.refresh_token);
}

/**
 * Retrieve the current access token (useful for checking auth state).
 */
export async function getAccessToken(): Promise<string | null> {
  return SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
}

/**
 * Clear tokens and reset auth state (used during logout).
 */
export async function logout(): Promise<void> {
  await clearTokens();
}

// Export the configured API client singleton
const apiClient = createApiClient();
export default apiClient;
