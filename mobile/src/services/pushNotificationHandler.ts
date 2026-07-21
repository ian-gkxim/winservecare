/**
 * Push Notification Handler for the WinServeCare Carer Mobile App.
 *
 * Handles registration with expo-notifications, device token submission to
 * the backend, and routing of incoming notifications to the correct handler
 * (schedule refresh or contextual question overlay).
 *
 * Falls back to in-app banners when push permission is denied.
 *
 * Requirements: 9.1, 9.2, 9.3, 9.5
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import apiClient from '@/services/apiClient';
import { ContextualQuestionPayload, DeviceTokenRequest } from '@/types';

// --- Types ---

export type NotificationType = 'schedule_change' | 'contextual_question';

export interface NotificationHandlers {
  onScheduleChange: () => void;
  onQuestion: (payload: ContextualQuestionPayload) => void;
}

interface PushNotificationData {
  type: NotificationType;
  payload?: ContextualQuestionPayload;
}

// --- Module State ---

let pushPermissionDenied = false;
let registeredHandlers: NotificationHandlers | null = null;
let notificationReceivedSubscription: Notifications.Subscription | null = null;
let notificationResponseSubscription: Notifications.Subscription | null = null;

/**
 * Navigation callback for tap-to-navigate behaviour.
 * Set externally by the app's navigation layer.
 */
let navigateToScreen: ((screen: string, params?: Record<string, unknown>) => void) | null = null;

/**
 * Register a navigation function for tap-to-navigate deep links.
 */
export function setNavigationCallback(
  callback: (screen: string, params?: Record<string, unknown>) => void
): void {
  navigateToScreen = callback;
}

// --- Core Functions ---

/**
 * Request push notification permissions and configure notification behaviour.
 *
 * Sets `pushPermissionDenied` flag if the user denies permission so the app
 * can fall back to in-app banners (Requirement 9.5).
 */
export async function initialize(): Promise<void> {
  // Configure how notifications appear when the app is in the foreground
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });

  const { status: existingStatus } = await Notifications.getPermissionsAsync();

  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    pushPermissionDenied = true;
    return;
  }

  pushPermissionDenied = false;

  // Set up notification listeners
  notificationReceivedSubscription = Notifications.addNotificationReceivedListener(
    handleNotificationReceived
  );

  notificationResponseSubscription = Notifications.addNotificationResponseReceivedListener(
    handleNotificationResponse
  );
}

/**
 * Register the device push token with the backend.
 * Should be called after successful authentication.
 *
 * @param authToken - The current access token (used only to confirm auth state;
 *   the apiClient attaches the token automatically via interceptors).
 */
export async function registerTokenWithBackend(authToken: string): Promise<void> {
  if (pushPermissionDenied) {
    return;
  }

  const tokenData = await Notifications.getExpoPushTokenAsync();
  const deviceToken = tokenData.data;

  const platform: DeviceTokenRequest['platform'] =
    Platform.OS === 'ios' ? 'ios' : 'android';

  const body: DeviceTokenRequest = {
    device_token: deviceToken,
    platform,
  };

  await apiClient.post('/api/mobile/auth/device-token', body);
}

/**
 * Register callbacks for different notification types.
 *
 * @param handlers.onScheduleChange - Called when a schedule update notification arrives.
 * @param handlers.onQuestion - Called with the question payload when a contextual question arrives.
 */
export function setNotificationHandlers(handlers: NotificationHandlers): void {
  registeredHandlers = handlers;
}

/**
 * Handle an incoming notification while the app is in the foreground.
 * Routes the notification data to the appropriate registered handler.
 */
export function handleNotificationReceived(
  notification: Notifications.Notification
): void {
  const data = notification.request.content.data as PushNotificationData | undefined;

  if (!data || !data.type) {
    return;
  }

  if (!registeredHandlers) {
    return;
  }

  switch (data.type) {
    case 'schedule_change':
      registeredHandlers.onScheduleChange();
      break;
    case 'contextual_question':
      if (data.payload) {
        registeredHandlers.onQuestion(data.payload);
      }
      break;
    default:
      // Unknown notification type — ignore
      break;
  }
}

/**
 * Handle a notification response (user tapped the notification).
 * Navigates to the relevant screen based on notification type (Requirement 9.3).
 *
 * - schedule_change → ScheduleScreen
 * - contextual_question → question prompt (QuestionScreen with payload)
 */
export function handleNotificationResponse(
  response: Notifications.NotificationResponse
): void {
  const data = response.notification.request.content.data as PushNotificationData | undefined;

  if (!data || !data.type) {
    return;
  }

  switch (data.type) {
    case 'schedule_change':
      navigateToScreen?.('ScheduleScreen');
      break;
    case 'contextual_question':
      if (data.payload) {
        // Also trigger the question handler if registered
        registeredHandlers?.onQuestion(data.payload);
        navigateToScreen?.('QuestionScreen', { question: data.payload });
      }
      break;
    default:
      break;
  }
}

/**
 * Returns whether push notifications are permitted on this device.
 * When false, the app should use in-app banners as a fallback.
 */
export function isPushEnabled(): boolean {
  return !pushPermissionDenied;
}

/**
 * Clean up notification listeners. Call on logout or app teardown.
 */
export function teardown(): void {
  notificationReceivedSubscription?.remove();
  notificationResponseSubscription?.remove();
  notificationReceivedSubscription = null;
  notificationResponseSubscription = null;
  registeredHandlers = null;
}
