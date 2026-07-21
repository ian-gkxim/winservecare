/**
 * SQLite-backed offline buffer for all outbound signals.
 *
 * Provides a FIFO queue that stores GPS, question response, and proactive input
 * signals locally when the device is offline. Signals are dequeued in chronological
 * order by their original captured_at timestamp for sync.
 *
 * Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
 */

import * as SQLite from 'expo-sqlite';

// --- Types ---

export type SignalType = 'gps' | 'question' | 'proactive';

export interface BufferedSignal {
  id: number;
  signal_type: SignalType;
  payload: object;
  captured_at: string; // ISO 8601 UTC — original device timestamp
  created_at: string;
}

// --- Constants ---

const DB_NAME = 'offline_buffer.db';
const CAPACITY_WARNING_THRESHOLD = 900;
const MIN_RETENTION_HOURS = 24;

// --- Module State ---

let db: SQLite.SQLiteDatabase | null = null;
let capacityWarningCallback: (() => void) | null = null;

/**
 * Initialise the SQLite database and create the signal_buffer table if needed.
 */
export async function initDatabase(): Promise<void> {
  db = await SQLite.openDatabaseAsync(DB_NAME);

  await db.execAsync(`
    CREATE TABLE IF NOT EXISTS signal_buffer (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      signal_type TEXT NOT NULL,
      payload TEXT NOT NULL,
      captured_at TEXT NOT NULL,
      synced INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL
    );
  `);

  // Index to support chronological dequeue of unsynced signals
  await db.execAsync(`
    CREATE INDEX IF NOT EXISTS idx_buffer_unsynced_order
    ON signal_buffer (synced, captured_at ASC);
  `);
}

/**
 * Store a signal in the offline buffer.
 *
 * After enqueue, checks the unsynced count and fires the capacity warning
 * callback if the threshold (900) is exceeded.
 */
export async function enqueue(
  signalType: SignalType,
  payload: object,
  capturedAt: string
): Promise<void> {
  assertInitialised();

  const now = new Date().toISOString();
  const payloadJson = JSON.stringify(payload);

  await db!.runAsync(
    `INSERT INTO signal_buffer (signal_type, payload, captured_at, created_at)
     VALUES (?, ?, ?, ?)`,
    [signalType, payloadJson, capturedAt, now]
  );

  // Check capacity and notify if approaching limit
  const count = await getCount();
  if (count > CAPACITY_WARNING_THRESHOLD && capacityWarningCallback) {
    capacityWarningCallback();
  }
}

/**
 * Retrieve unsynced signals in chronological order (oldest first).
 *
 * @param limit Maximum number of signals to return. Defaults to 50.
 */
export async function dequeue(limit: number = 50): Promise<BufferedSignal[]> {
  assertInitialised();

  const rows = await db!.getAllAsync<{
    id: number;
    signal_type: string;
    payload: string;
    captured_at: string;
    created_at: string;
  }>(
    `SELECT id, signal_type, payload, captured_at, created_at
     FROM signal_buffer
     WHERE synced = 0
     ORDER BY captured_at ASC
     LIMIT ?`,
    [limit]
  );

  return rows.map((row) => ({
    id: row.id,
    signal_type: row.signal_type as SignalType,
    payload: JSON.parse(row.payload),
    captured_at: row.captured_at,
    created_at: row.created_at,
  }));
}

/**
 * Mark the given signal IDs as successfully synced.
 */
export async function markSynced(ids: number[]): Promise<void> {
  assertInitialised();

  if (ids.length === 0) return;

  const placeholders = ids.map(() => '?').join(',');
  await db!.runAsync(
    `UPDATE signal_buffer SET synced = 1 WHERE id IN (${placeholders})`,
    ids
  );
}

/**
 * Get the count of unsynced signals in the buffer.
 */
export async function getCount(): Promise<number> {
  assertInitialised();

  const result = await db!.getFirstAsync<{ count: number }>(
    `SELECT COUNT(*) as count FROM signal_buffer WHERE synced = 0`
  );

  return result?.count ?? 0;
}

/**
 * Remove synced signals that are older than the minimum retention period (24 hours).
 *
 * Signals that have not been synced are never removed regardless of age.
 */
export async function cleanup(): Promise<void> {
  assertInitialised();

  const cutoff = new Date(Date.now() - MIN_RETENTION_HOURS * 60 * 60 * 1000).toISOString();

  await db!.runAsync(
    `DELETE FROM signal_buffer WHERE synced = 1 AND created_at < ?`,
    [cutoff]
  );
}

/**
 * Register a callback that fires when the buffer exceeds 900 unsynced signals.
 */
export function onCapacityWarning(callback: () => void): void {
  capacityWarningCallback = callback;
}

/**
 * Close the database connection. Useful for testing teardown.
 */
export async function closeDatabase(): Promise<void> {
  if (db) {
    await db.closeAsync();
    db = null;
  }
}

// --- Internal Helpers ---

function assertInitialised(): asserts db is SQLite.SQLiteDatabase {
  if (!db) {
    throw new Error(
      'OfflineBuffer: database not initialised. Call initDatabase() first.'
    );
  }
}
