/**
 * Local SQLite cache for the carer's daily schedule.
 *
 * Uses expo-sqlite to store visits so the schedule is available offline.
 * The cache is cleared and repopulated whenever fresh data is fetched from
 * the backend.
 *
 * Requirements: 2.5, 8.1
 */

import * as SQLite from 'expo-sqlite';

import { MobileVisitSummary, VisitStatus } from '@/types';

const DB_NAME = 'schedule_cache.db';

let db: SQLite.SQLiteDatabase | null = null;

/**
 * Open (or create) the local database and ensure the schema exists.
 */
async function getDatabase(): Promise<SQLite.SQLiteDatabase> {
  if (db) return db;

  db = await SQLite.openDatabaseAsync(DB_NAME);

  await db.execAsync(`
    CREATE TABLE IF NOT EXISTS cached_visits (
      id INTEGER PRIMARY KEY,
      patient_name TEXT NOT NULL,
      patient_address TEXT NOT NULL,
      patient_lat REAL NOT NULL,
      patient_lng REAL NOT NULL,
      window_start TEXT NOT NULL,
      window_end TEXT NOT NULL,
      duration_minutes INTEGER NOT NULL,
      required_skills TEXT NOT NULL,
      status TEXT NOT NULL,
      confidence_score INTEGER NOT NULL,
      cached_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);

  return db;
}

/**
 * Replace the entire local cache with a fresh set of visits.
 * Called after a successful schedule fetch from the backend.
 */
export async function cacheSchedule(visits: MobileVisitSummary[]): Promise<void> {
  const database = await getDatabase();

  await database.execAsync('DELETE FROM cached_visits;');

  for (const visit of visits) {
    await database.runAsync(
      `INSERT INTO cached_visits
        (id, patient_name, patient_address, patient_lat, patient_lng,
         window_start, window_end, duration_minutes, required_skills,
         status, confidence_score)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
      [
        visit.id,
        visit.patient_name,
        visit.patient_address,
        visit.patient_lat,
        visit.patient_lng,
        visit.window_start,
        visit.window_end,
        visit.duration_minutes,
        JSON.stringify(visit.required_skills),
        visit.status,
        visit.confidence_score,
      ]
    );
  }
}

/**
 * Maximum cache age in milliseconds (24 hours).
 * Cached data older than this is considered stale and discarded.
 */
const CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000;

/**
 * Retrieve the cached schedule for offline display.
 * Returns visits sorted by window_start (ascending).
 * Cache is invalidated if older than 24 hours.
 */
export async function getCachedSchedule(): Promise<MobileVisitSummary[]> {
  const database = await getDatabase();

  // Check cache age — invalidate if older than 24 hours
  const oldest = await database.getFirstAsync<{ cached_at: string }>(
    'SELECT cached_at FROM cached_visits ORDER BY cached_at ASC LIMIT 1;'
  );

  if (oldest?.cached_at) {
    const cachedTime = new Date(oldest.cached_at + 'Z').getTime();
    const now = Date.now();
    if (now - cachedTime > CACHE_MAX_AGE_MS) {
      // Cache is stale — clear it and return empty
      await database.execAsync('DELETE FROM cached_visits;');
      return [];
    }
  }

  const rows = await database.getAllAsync<{
    id: number;
    patient_name: string;
    patient_address: string;
    patient_lat: number;
    patient_lng: number;
    window_start: string;
    window_end: string;
    duration_minutes: number;
    required_skills: string;
    status: string;
    confidence_score: number;
  }>('SELECT * FROM cached_visits ORDER BY window_start ASC;');

  return rows.map((row) => ({
    id: row.id,
    patient_name: row.patient_name,
    patient_address: row.patient_address,
    patient_lat: row.patient_lat,
    patient_lng: row.patient_lng,
    window_start: row.window_start,
    window_end: row.window_end,
    duration_minutes: row.duration_minutes,
    required_skills: JSON.parse(row.required_skills) as string[],
    status: row.status as VisitStatus,
    confidence_score: row.confidence_score,
  }));
}

/**
 * Clear the local schedule cache entirely.
 */
export async function clearScheduleCache(): Promise<void> {
  const database = await getDatabase();
  await database.execAsync('DELETE FROM cached_visits;');
}
