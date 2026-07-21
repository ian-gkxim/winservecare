/**
 * Connectivity-aware sync manager for the offline buffer.
 *
 * Listens for network state changes and synchronises buffered signals to the
 * backend when connectivity is available. Implements exponential backoff on
 * failure, GPS signal batching, and preserves original captured_at timestamps.
 *
 * Requirements: 8.2, 8.3, 8.4, 8.5, 10.2
 */

import NetInfo, { NetInfoState } from '@react-native-community/netinfo';

import apiClient from '@/services/apiClient';
import {
  BufferedSignal,
  dequeue,
  getCount,
  markSynced,
} from '@/services/offlineBuffer';
import { GPSBatch } from '@/types';

// --- Constants ---

const BASE_BACKOFF_MS = 30_000; // 30 seconds
const MAX_ATTEMPTS = 5;
const SYNC_DELAY_MS = 5_000; // Start sync attempt within 30s; we use 5s for responsiveness
const BATCH_SIZE = 50; // Signals per dequeue batch

// --- Types ---

type SyncErrorCallback = (error: Error, remainingAttempts: number) => void;

// --- Module State ---

let isRunning = false;
let isSyncing = false;
let syncTimeoutId: ReturnType<typeof setTimeout> | null = null;
let unsubscribeNetInfo: (() => void) | null = null;
let errorCallback: SyncErrorCallback | null = null;
let consecutiveFailures = 0;

/**
 * Start the sync queue. Subscribes to connectivity changes and triggers
 * sync when the device comes back online.
 */
export function startSync(): void {
  if (isRunning) return;
  isRunning = true;
  consecutiveFailures = 0;

  unsubscribeNetInfo = NetInfo.addEventListener(handleConnectivityChange);

  // Attempt an initial sync in case we're already online
  scheduleSyncAttempt();
}

/**
 * Stop the sync queue. Unsubscribes from connectivity events and cancels
 * any pending sync timers.
 */
export function stopSync(): void {
  isRunning = false;

  if (unsubscribeNetInfo) {
    unsubscribeNetInfo();
    unsubscribeNetInfo = null;
  }

  if (syncTimeoutId) {
    clearTimeout(syncTimeoutId);
    syncTimeoutId = null;
  }
}

/**
 * Register a callback invoked when sync fails.
 * The callback receives the error and the number of remaining retry attempts.
 */
export function onSyncError(callback: SyncErrorCallback): void {
  errorCallback = callback;
}

// --- Internal Logic ---

/**
 * Handle connectivity state changes from NetInfo.
 * When connectivity is restored, schedule a sync within 30 seconds.
 */
function handleConnectivityChange(state: NetInfoState): void {
  if (state.isConnected && state.isInternetReachable !== false) {
    scheduleSyncAttempt();
  }
}

/**
 * Schedule a sync attempt after a short delay (within the 30s requirement).
 */
function scheduleSyncAttempt(): void {
  if (!isRunning || syncTimeoutId) return;

  syncTimeoutId = setTimeout(async () => {
    syncTimeoutId = null;
    await attemptSync();
  }, SYNC_DELAY_MS);
}

/**
 * Core sync loop. Dequeues buffered signals and transmits them to the backend.
 * GPS signals with 3+ pending are batched into a single request.
 * Other signals are sent individually.
 */
async function attemptSync(): Promise<void> {
  if (!isRunning || isSyncing) return;

  // Verify connectivity before starting
  const netState = await NetInfo.fetch();
  if (!netState.isConnected || netState.isInternetReachable === false) {
    return;
  }

  isSyncing = true;

  try {
    let hasMore = true;

    while (hasMore && isRunning) {
      const signals = await dequeue(BATCH_SIZE);

      if (signals.length === 0) {
        hasMore = false;
        break;
      }

      // Separate GPS signals from other types
      const gpsSignals = signals.filter((s) => s.signal_type === 'gps');
      const otherSignals = signals.filter((s) => s.signal_type !== 'gps');

      // GPS batching: 3+ GPS signals → single batch request
      if (gpsSignals.length >= 3) {
        await sendGPSBatch(gpsSignals);
      } else {
        // Fewer than 3 GPS signals: send individually
        for (const signal of gpsSignals) {
          await sendIndividualSignal(signal);
        }
      }

      // Question and proactive signals: send individually
      for (const signal of otherSignals) {
        await sendIndividualSignal(signal);
      }

      // Mark all as synced on success
      const syncedIds = signals.map((s) => s.id);
      await markSynced(syncedIds);

      // Reset failure counter on success
      consecutiveFailures = 0;

      // Check if there are more signals to sync
      const remaining = await getCount();
      hasMore = remaining > 0;
    }
  } catch (error) {
    await handleSyncFailure(error as Error);
  } finally {
    isSyncing = false;
  }
}

/**
 * Send a batch of GPS signals as a single API request.
 * Preserves original captured_at timestamps.
 */
async function sendGPSBatch(signals: BufferedSignal[]): Promise<void> {
  const batch: GPSBatch = {
    signals: signals.map((s) => ({
      ...s.payload as object,
      captured_at: s.captured_at, // Preserve original timestamp
    })) as GPSBatch['signals'],
  };

  await apiClient.post('/api/mobile/signals/gps', batch);
}

/**
 * Send a single signal to the appropriate endpoint.
 * Preserves original captured_at timestamp.
 */
async function sendIndividualSignal(signal: BufferedSignal): Promise<void> {
  const endpointMap: Record<string, string> = {
    gps: '/api/mobile/signals/gps',
    question: '/api/mobile/signals/question',
    proactive: '/api/mobile/signals/proactive',
  };

  const endpoint = endpointMap[signal.signal_type];
  const payload = {
    ...signal.payload,
    captured_at: signal.captured_at, // Preserve original timestamp
  };

  await apiClient.post(endpoint, payload);
}

/**
 * Handle a sync failure with exponential backoff.
 *
 * Backoff schedule: 30s, 60s, 120s, 240s, 480s
 * After MAX_ATTEMPTS consecutive failures, alert the carer via the error callback.
 * Signals are always retained regardless of retry outcome.
 */
async function handleSyncFailure(error: Error): Promise<void> {
  consecutiveFailures++;

  const remainingAttempts = MAX_ATTEMPTS - consecutiveFailures;

  if (errorCallback) {
    errorCallback(error, Math.max(0, remainingAttempts));
  }

  if (consecutiveFailures >= MAX_ATTEMPTS) {
    // Max attempts reached — alert carer, stop retrying until next connectivity event
    consecutiveFailures = 0;
    return;
  }

  // Schedule retry with exponential backoff
  const backoffMs = BASE_BACKOFF_MS * Math.pow(2, consecutiveFailures - 1);

  if (isRunning) {
    syncTimeoutId = setTimeout(async () => {
      syncTimeoutId = null;
      await attemptSync();
    }, backoffMs);
  }
}
