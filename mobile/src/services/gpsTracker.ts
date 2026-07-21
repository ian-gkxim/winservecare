/**
 * GPS Tracker Service for the WinServeCare Carer Mobile App.
 *
 * Manages background location tracking with adaptive frequency,
 * geofence-based proximity detection, battery-aware power saving,
 * and driving speed calculation.
 *
 * All GPS signals are piped to the Offline Buffer for reliable delivery.
 *
 * Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 10.1, 10.3, 10.5
 */

import BackgroundGeolocation, {
  Location,
  GeofenceEvent,
  MotionChangeEvent,
} from 'react-native-background-geolocation';
import { AppState, AppStateStatus, Platform } from 'react-native';

import { GPSSignal, MobileVisitSummary } from '@/types';

// --- Constants ---

/** Standard GPS collection interval (seconds) */
const STANDARD_INTERVAL_SEC = 60;

/** Near-geofence GPS collection interval (seconds) */
const NEAR_VISIT_INTERVAL_SEC = 15;

/** Power-saving GPS collection interval (seconds) */
const POWER_SAVING_INTERVAL_SEC = 300; // 5 minutes

/** Geofence entry radius in metres */
const GEOFENCE_ENTRY_RADIUS_M = 100;

/** Geofence exit radius in metres (hysteresis to prevent flapping) */
const GEOFENCE_EXIT_RADIUS_M = 150;

/** Low-accuracy threshold in metres */
const LOW_ACCURACY_THRESHOLD_M = 50;

/** Battery threshold below which power-saving mode activates */
const BATTERY_LOW_THRESHOLD = 0.15;

/** Battery threshold above which normal mode resumes */
const BATTERY_RECOVERY_THRESHOLD = 0.20;

/** No-visit-within threshold in milliseconds (2 hours) */
const NO_VISIT_WINDOW_MS = 2 * 60 * 60 * 1000;

// --- Types ---

export type GPSFrequencyMode = 'standard' | 'near_visit' | 'power_saving';

export interface GPSTrackerSignal extends GPSSignal {
  speed_kmh: number;
  geofence_state: 'inside' | 'near' | 'outside';
  frequency_mode: GPSFrequencyMode;
  nearest_visit_id?: number;
}

export type SignalCallback = (signal: GPSTrackerSignal) => void;

// --- GPS Tracker ---

class GPSTracker {
  private tracking = false;
  private visits: MobileVisitSummary[] = [];
  private signalCallbacks: SignalCallback[] = [];
  private currentSpeed = 0; // km/h
  private currentFrequencyMode: GPSFrequencyMode = 'standard';
  private batteryLevel = 1.0;
  private isLowBattery = false;
  private nearVisitId: number | undefined;
  private insideGeofenceVisitIds: Set<number> = new Set();
  private appStateSubscription: { remove: () => void } | null = null;
  private batteryCheckInterval: ReturnType<typeof setInterval> | null = null;

  /**
   * Start GPS tracking with adaptive frequency and geofencing for the given visits.
   *
   * Configures geofences around each scheduled visit address and begins
   * background location collection at the appropriate frequency.
   */
  async start(visits: MobileVisitSummary[]): Promise<void> {
    if (this.tracking) {
      // Already tracking — update visits and geofences
      await this.updateVisits(visits);
      return;
    }

    this.visits = visits;
    this.tracking = true;
    this.insideGeofenceVisitIds.clear();

    // Determine initial frequency mode
    this.currentFrequencyMode = this.determineFrequencyMode();

    // Configure background geolocation
    await BackgroundGeolocation.ready({
      desiredAccuracy: BackgroundGeolocation.DESIRED_ACCURACY_HIGH,
      distanceFilter: 10,
      locationUpdateInterval: this.getIntervalMs(),
      fastestLocationUpdateInterval: NEAR_VISIT_INTERVAL_SEC * 1000,
      stopOnTerminate: false,
      startOnBoot: false,
      enableHeadless: true,
      // Battery-aware settings
      preventSuspend: true,
      heartbeatInterval: this.getIntervalSec(),
    });

    // Register event listeners
    BackgroundGeolocation.onLocation(this.handleLocation.bind(this));
    BackgroundGeolocation.onGeofence(this.handleGeofence.bind(this));
    BackgroundGeolocation.onMotionChange(this.handleMotionChange.bind(this));

    // Add geofences for all visit addresses
    await this.addGeofences(visits);

    // Start tracking
    await BackgroundGeolocation.start();

    // Start battery monitoring
    this.startBatteryMonitoring();

    // Listen for app state changes to trigger battery checks
    this.appStateSubscription = AppState.addEventListener(
      'change',
      this.handleAppStateChange.bind(this)
    );
  }

  /**
   * Stop GPS tracking and remove all geofences.
   */
  async stop(): Promise<void> {
    if (!this.tracking) return;

    this.tracking = false;
    this.visits = [];
    this.insideGeofenceVisitIds.clear();
    this.nearVisitId = undefined;
    this.currentSpeed = 0;

    // Remove all geofences
    await BackgroundGeolocation.removeGeofences();

    // Stop background geolocation
    await BackgroundGeolocation.stop();

    // Remove event listeners
    BackgroundGeolocation.removeListeners();

    // Stop battery monitoring
    this.stopBatteryMonitoring();

    // Remove app state listener
    if (this.appStateSubscription) {
      this.appStateSubscription.remove();
      this.appStateSubscription = null;
    }
  }

  /**
   * Register a callback to receive new GPS signals.
   * Signals are piped to the Offline Buffer via this mechanism.
   */
  onSignal(callback: SignalCallback): () => void {
    this.signalCallbacks.push(callback);
    // Return unsubscribe function
    return () => {
      this.signalCallbacks = this.signalCallbacks.filter((cb) => cb !== callback);
    };
  }

  /**
   * Get the current GPS speed in km/h.
   * Used by the Question Handler for driving detection (suppress questions > 10 km/h).
   */
  getCurrentSpeed(): number {
    return this.currentSpeed;
  }

  /**
   * Returns whether GPS tracking is currently active.
   */
  isTracking(): boolean {
    return this.tracking;
  }

  /**
   * Get the current frequency mode for diagnostics/display.
   */
  getCurrentFrequencyMode(): GPSFrequencyMode {
    return this.currentFrequencyMode;
  }

  /**
   * Get the current battery level (0-1).
   */
  getBatteryLevel(): number {
    return this.batteryLevel;
  }

  /**
   * Update the list of scheduled visits and reconfigure geofences.
   */
  async updateVisits(visits: MobileVisitSummary[]): Promise<void> {
    this.visits = visits;

    // Remove existing geofences and add new ones
    await BackgroundGeolocation.removeGeofences();
    this.insideGeofenceVisitIds.clear();
    this.nearVisitId = undefined;

    await this.addGeofences(visits);

    // Recalculate frequency mode based on new visits
    await this.updateFrequency();
  }

  // --- Private Methods ---

  /**
   * Handle a new location event from the background geolocation plugin.
   */
  private handleLocation(location: Location): void {
    if (!this.tracking) return;

    // Calculate speed in km/h from m/s
    const speedMs = location.coords.speed ?? 0;
    this.currentSpeed = Math.max(0, speedMs * 3.6);

    // Determine geofence state and nearest visit
    const { geofenceState, nearestVisitId } = this.evaluateProximity(
      location.coords.latitude,
      location.coords.longitude
    );

    // Check if accuracy is low
    const accuracy = location.coords.accuracy ?? 0;
    const isLowAccuracy = accuracy > LOW_ACCURACY_THRESHOLD_M;

    // Build the signal
    const signal: GPSTrackerSignal = {
      latitude: location.coords.latitude,
      longitude: location.coords.longitude,
      accuracy_metres: accuracy,
      low_accuracy: isLowAccuracy,
      captured_at: new Date(location.timestamp).toISOString(),
      speed_kmh: this.currentSpeed,
      geofence_state: geofenceState,
      frequency_mode: this.currentFrequencyMode,
      nearest_visit_id: nearestVisitId,
    };

    // Emit signal to all registered callbacks (→ Offline Buffer)
    this.emitSignal(signal);

    // Update frequency if proximity changed
    if (geofenceState === 'inside' || geofenceState === 'near') {
      if (this.nearVisitId !== nearestVisitId) {
        this.nearVisitId = nearestVisitId;
        this.updateFrequency();
      }
    } else if (this.nearVisitId !== undefined) {
      this.nearVisitId = undefined;
      this.updateFrequency();
    }
  }

  /**
   * Handle geofence entry/exit events.
   */
  private handleGeofence(event: GeofenceEvent): void {
    if (!this.tracking) return;

    const visitId = parseInt(event.identifier, 10);
    if (isNaN(visitId)) return;

    if (event.action === 'ENTER') {
      this.insideGeofenceVisitIds.add(visitId);
      this.nearVisitId = visitId;
    } else if (event.action === 'EXIT') {
      this.insideGeofenceVisitIds.delete(visitId);
      if (this.nearVisitId === visitId) {
        this.nearVisitId = undefined;
      }
    }

    // Update frequency based on new geofence state
    this.updateFrequency();
  }

  /**
   * Handle motion change events (moving/stationary transitions).
   */
  private handleMotionChange(event: MotionChangeEvent): void {
    if (!this.tracking) return;

    if (event.location) {
      this.handleLocation(event.location);
    }
  }

  /**
   * Handle app state changes for battery monitoring.
   */
  private handleAppStateChange(nextState: AppStateStatus): void {
    if (nextState === 'active') {
      this.checkBattery();
    }
  }

  /**
   * Add geofences for all scheduled visit addresses.
   * Uses entry radius of 100m and exit (notify-on-exit) at 150m.
   */
  private async addGeofences(visits: MobileVisitSummary[]): Promise<void> {
    const geofences = visits.map((visit) => ({
      identifier: String(visit.id),
      latitude: visit.patient_lat,
      longitude: visit.patient_lng,
      radius: GEOFENCE_ENTRY_RADIUS_M,
      notifyOnEntry: true,
      notifyOnExit: true,
      // Use loitering delay to avoid spurious triggers
      loiteringDelay: 0,
      extras: {
        visit_id: visit.id,
        exit_radius: GEOFENCE_EXIT_RADIUS_M,
      },
    }));

    if (geofences.length > 0) {
      await BackgroundGeolocation.addGeofences(geofences);
    }
  }

  /**
   * Evaluate proximity to all visit addresses and return the current geofence state.
   */
  private evaluateProximity(
    lat: number,
    lng: number
  ): { geofenceState: 'inside' | 'near' | 'outside'; nearestVisitId?: number } {
    let minDistance = Infinity;
    let nearestId: number | undefined;

    for (const visit of this.visits) {
      const distance = this.haversineDistance(
        lat,
        lng,
        visit.patient_lat,
        visit.patient_lng
      );

      if (distance < minDistance) {
        minDistance = distance;
        nearestId = visit.id;
      }
    }

    if (minDistance <= GEOFENCE_ENTRY_RADIUS_M) {
      return { geofenceState: 'inside', nearestVisitId: nearestId };
    }

    if (minDistance <= GEOFENCE_EXIT_RADIUS_M) {
      return { geofenceState: 'near', nearestVisitId: nearestId };
    }

    return { geofenceState: 'outside', nearestVisitId: nearestId };
  }

  /**
   * Calculate Haversine distance between two coordinates in metres.
   */
  private haversineDistance(
    lat1: number,
    lng1: number,
    lat2: number,
    lng2: number
  ): number {
    const R = 6371000; // Earth radius in metres
    const toRad = (deg: number) => (deg * Math.PI) / 180;

    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) *
        Math.cos(toRad(lat2)) *
        Math.sin(dLng / 2) *
        Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  }

  /**
   * Determine the appropriate frequency mode based on current context.
   *
   * Priority (highest to lowest):
   * 1. Within 100m of a visit address → 15s (near_visit)
   * 2. Battery < 15% OR no visit within 2 hours → 5min (power_saving)
   * 3. Default → 60s (standard)
   */
  private determineFrequencyMode(): GPSFrequencyMode {
    // Priority 1: Near a visit address
    if (this.insideGeofenceVisitIds.size > 0 || this.nearVisitId !== undefined) {
      return 'near_visit';
    }

    // Priority 2: Low battery
    if (this.isLowBattery) {
      return 'power_saving';
    }

    // Priority 2: No visit within 2 hours
    if (this.hasNoUpcomingVisit()) {
      return 'power_saving';
    }

    // Priority 3: Default
    return 'standard';
  }

  /**
   * Check if there is no upcoming visit within the next 2 hours.
   */
  private hasNoUpcomingVisit(): boolean {
    if (this.visits.length === 0) return true;

    const now = Date.now();
    const twoHoursFromNow = now + NO_VISIT_WINDOW_MS;

    return !this.visits.some((visit) => {
      const visitStart = new Date(visit.window_start).getTime();
      return visitStart >= now && visitStart <= twoHoursFromNow;
    });
  }

  /**
   * Get the interval in seconds for the current frequency mode.
   */
  private getIntervalSec(): number {
    switch (this.currentFrequencyMode) {
      case 'near_visit':
        return NEAR_VISIT_INTERVAL_SEC;
      case 'power_saving':
        return POWER_SAVING_INTERVAL_SEC;
      case 'standard':
      default:
        return STANDARD_INTERVAL_SEC;
    }
  }

  /**
   * Get the interval in milliseconds for the current frequency mode.
   */
  private getIntervalMs(): number {
    return this.getIntervalSec() * 1000;
  }

  /**
   * Update the GPS collection frequency based on current context.
   */
  private async updateFrequency(): Promise<void> {
    const newMode = this.determineFrequencyMode();
    if (newMode === this.currentFrequencyMode) return;

    this.currentFrequencyMode = newMode;

    // Reconfigure the background geolocation plugin with new interval
    await BackgroundGeolocation.setConfig({
      locationUpdateInterval: this.getIntervalMs(),
      heartbeatInterval: this.getIntervalSec(),
    });
  }

  /**
   * Start periodic battery level monitoring.
   */
  private startBatteryMonitoring(): void {
    // Check battery immediately
    this.checkBattery();

    // Check battery every 60 seconds
    this.batteryCheckInterval = setInterval(() => {
      this.checkBattery();
    }, 60_000);
  }

  /**
   * Stop battery monitoring.
   */
  private stopBatteryMonitoring(): void {
    if (this.batteryCheckInterval) {
      clearInterval(this.batteryCheckInterval);
      this.batteryCheckInterval = null;
    }
  }

  /**
   * Check current battery level and update tracking frequency accordingly.
   *
   * - Battery < 15%: Switch to power-saving mode (5min interval)
   * - Battery recovers above 20%: Resume context-based frequency
   *
   * Uses react-native-background-geolocation's built-in battery monitoring
   * which is available on both iOS and Android.
   */
  private async checkBattery(): Promise<void> {
    try {
      const state = await BackgroundGeolocation.getState();
      // Battery level is a value between 0 and 1
      const level = state.battery?.level ?? 1.0;
      this.batteryLevel = level;

      const wasLowBattery = this.isLowBattery;

      if (level < BATTERY_LOW_THRESHOLD) {
        this.isLowBattery = true;
      } else if (level >= BATTERY_RECOVERY_THRESHOLD) {
        // Hysteresis: only recover when above 20%
        this.isLowBattery = false;
      }
      // Between 15% and 20%: maintain current state (hysteresis)

      // If battery state changed, update frequency
      if (wasLowBattery !== this.isLowBattery) {
        await this.updateFrequency();
      }
    } catch {
      // Battery check failed — continue with current settings
    }
  }

  /**
   * Emit a GPS signal to all registered callbacks.
   */
  private emitSignal(signal: GPSTrackerSignal): void {
    for (const callback of this.signalCallbacks) {
      try {
        callback(signal);
      } catch {
        // Don't let a failing callback break the signal pipeline
      }
    }
  }
}

// Export singleton instance
export const gpsTracker = new GPSTracker();

export default gpsTracker;
