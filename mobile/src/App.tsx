/**
 * WinServeCare Carer Mobile App — Root Application Component.
 *
 * Wires all mobile components together:
 * - Navigation (Auth stack → Main stack) with conditional rendering
 * - GPS Tracker → Offline Buffer → Sync Queue → Backend Signal API
 * - Push Notification Handler → Question Handler / Schedule refresh
 * - Proactive Input → Offline Buffer → Sync Queue
 * - Auth token availability before service initialization
 * - Persistent offline indicator in main navigation
 * - Session expired callback triggers logout
 *
 * Requirements: 1.3, 3.2, 5.4, 8.1, 9.3
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { NavigationContainer, NavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import NetInfo from '@react-native-community/netinfo';

import LoginScreen from '@/screens/LoginScreen';
import ScheduleScreen from '@/screens/ScheduleScreen';
import VisitDetailScreen from '@/screens/VisitDetailScreen';
import ProactiveInputFAB from '@/components/ProactiveInputFAB';
import QuestionOverlay from '@/components/QuestionOverlay';

import { isAuthenticated, startSilentRefreshTimer, stopSilentRefreshTimer } from '@/services/authService';
import { logout as authLogout } from '@/services/authService';
import { getAccessToken, setSessionExpiredCallback } from '@/services/apiClient';
import { initDatabase, enqueue } from '@/services/offlineBuffer';
import { gpsTracker } from '@/services/gpsTracker';
import {
  initialize as initPushNotifications,
  registerTokenWithBackend,
  setNotificationHandlers,
  setNavigationCallback,
  teardown as teardownPush,
} from '@/services/pushNotificationHandler';
import {
  handleIncomingQuestion,
  onQuestionReady,
  updateGpsSpeed,
  getActiveQuestion,
} from '@/services/questionHandler';
import { startSync, stopSync } from '@/services/syncQueue';
import apiClient from '@/services/apiClient';
import { ContextualQuestionPayload, MobileVisitSummary } from '@/types';

// --- Navigation Types ---

export type AuthStackParamList = {
  Login: undefined;
};

export type MainStackParamList = {
  Schedule: undefined;
  VisitDetail: { visitId: number; visit: MobileVisitSummary };
};

// --- Stack Navigators ---

const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const MainStack = createNativeStackNavigator<MainStackParamList>();

// --- Auth Navigator ---

function AuthNavigator({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login">
        {() => <LoginScreen onLoginSuccess={onLoginSuccess} />}
      </AuthStack.Screen>
    </AuthStack.Navigator>
  );
}

// --- Main Navigator ---

function MainNavigator({ isOffline }: { isOffline: boolean }) {
  return (
    <View style={styles.mainContainer}>
      {/* Persistent offline indicator banner */}
      {isOffline && (
        <View style={styles.offlineBanner} accessibilityRole="alert">
          <Text style={styles.offlineBannerText}>
            Offline — data will sync when connection is restored
          </Text>
        </View>
      )}

      <MainStack.Navigator
        screenOptions={{
          headerStyle: styles.header,
          headerTitleStyle: styles.headerTitle,
          headerTintColor: '#333',
        }}
      >
        <MainStack.Screen
          name="Schedule"
          component={ScheduleScreen}
          options={{ title: 'Today\'s Visits' }}
        />
        <MainStack.Screen
          name="VisitDetail"
          component={VisitDetailScreen}
          options={{ title: 'Visit Details' }}
        />
      </MainStack.Navigator>

      {/* Proactive Input FAB visible on all main stack screens */}
      <ProactiveInputFAB />
    </View>
  );
}

// --- Root App Component ---

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [activeQuestion, setActiveQuestion] = useState<ContextualQuestionPayload | null>(null);

  const navigationRef = useRef<NavigationContainerRef<MainStackParamList>>(null);
  const gpsUnsubscribeRef = useRef<(() => void) | null>(null);

  // --- Check existing auth on app start ---
  useEffect(() => {
    async function checkAuth() {
      try {
        const authenticated = await isAuthenticated();
        if (authenticated) {
          setIsLoggedIn(true);
          await initializeServices();
        }
      } catch {
        // Not authenticated, show login
      } finally {
        setIsCheckingAuth(false);
      }
    }
    checkAuth();
  }, []);

  // --- Network connectivity monitoring ---
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      setIsOffline(!state.isConnected || state.isInternetReachable === false);
    });
    return () => unsubscribe();
  }, []);

  // --- Set session expired callback to trigger logout ---
  useEffect(() => {
    setSessionExpiredCallback(() => {
      handleLogout();
    });
  }, []);

  // --- Question handler: wire question ready callback to state ---
  useEffect(() => {
    onQuestionReady((question) => {
      setActiveQuestion(question);
    });
  }, []);

  // --- Service Initialization (after login) ---
  const initializeServices = useCallback(async () => {
    try {
      // 1. Initialize offline buffer database
      await initDatabase();

      // 1.5. Start silent refresh timer (periodic check for token expiry)
      startSilentRefreshTimer();

      // 2. Register push notifications
      await initPushNotifications();
      const token = await getAccessToken();
      if (token) {
        await registerTokenWithBackend(token);
      }

      // 3. Wire push notification handlers → question handler and schedule refresh
      setNotificationHandlers({
        onScheduleChange: () => {
          // Trigger schedule refresh — ScheduleScreen auto-refreshes via its own interval,
          // but we can force immediate navigation/refresh via the nav callback
          if (navigationRef.current) {
            navigationRef.current.navigate('Schedule');
          }
        },
        onQuestion: (payload: ContextualQuestionPayload) => {
          handleIncomingQuestion(payload);
        },
      });

      // 4. Wire push notification navigation callback
      setNavigationCallback((screen: string, params?: Record<string, unknown>) => {
        if (navigationRef.current) {
          navigationRef.current.navigate(screen as any, params as any);
        }
      });

      // 5. Start GPS tracker with today's visits
      try {
        const response = await apiClient.get<MobileVisitSummary[]>('/api/mobile/schedule');
        const visits = response.data;
        await gpsTracker.start(visits);
      } catch {
        // If schedule fetch fails, start GPS without visits (standard frequency)
        await gpsTracker.start([]);
      }

      // 6. Wire GPS tracker signals → offline buffer
      gpsUnsubscribeRef.current = gpsTracker.onSignal((signal) => {
        enqueue('gps', signal, signal.captured_at);
        // Wire GPS speed updates → question handler for driving suppression
        updateGpsSpeed(signal.speed_kmh);
      });

      // 7. Start sync queue
      startSync();
    } catch {
      // Service initialization failure is non-fatal — app can function
      // partially without GPS/push. Offline buffer is critical but rarely fails.
    }
  }, []);

  // --- Login Success Handler ---
  const handleLoginSuccess = useCallback(async () => {
    setIsLoggedIn(true);
    await initializeServices();
  }, [initializeServices]);

  // --- Logout Handler ---
  const handleLogout = useCallback(async () => {
    // Stop GPS tracker
    await gpsTracker.stop();
    if (gpsUnsubscribeRef.current) {
      gpsUnsubscribeRef.current();
      gpsUnsubscribeRef.current = null;
    }

    // Stop sync queue
    stopSync();

    // Stop silent refresh timer
    stopSilentRefreshTimer();

    // Tear down push notifications
    teardownPush();

    // Clear auth state
    await authLogout();

    // Clear question state
    setActiveQuestion(null);

    // Navigate back to login
    setIsLoggedIn(false);
  }, []);

  // --- Loading state while checking auth ---
  if (isCheckingAuth) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.loadingText}>WinServeCare</Text>
      </View>
    );
  }

  return (
    <NavigationContainer ref={navigationRef}>
      {isLoggedIn ? (
        <View style={styles.rootContainer}>
          <MainNavigator isOffline={isOffline} />

          {/* Question Overlay at top level — driven by questionHandler */}
          <QuestionOverlay
            question={activeQuestion}
            onDismiss={() => setActiveQuestion(null)}
          />
        </View>
      ) : (
        <AuthNavigator onLoginSuccess={handleLoginSuccess} />
      )}
    </NavigationContainer>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  rootContainer: {
    flex: 1,
  },
  mainContainer: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1a1a2e',
  },
  offlineBanner: {
    backgroundColor: '#FF9800',
    paddingVertical: 6,
    paddingHorizontal: 16,
    alignItems: 'center',
    zIndex: 100,
  },
  offlineBannerText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  header: {
    backgroundColor: '#FFFFFF',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1a1a2e',
  },
});
