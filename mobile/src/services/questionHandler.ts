/**
 * Question Handler Service — processes incoming contextual question payloads.
 *
 * Responsibilities:
 * - Receives question payloads from push notifications
 * - Suppresses questions while carer is driving (GPS speed > 10 km/h)
 * - Queues suppressed questions (max 10) for later display
 * - Releases queued questions when speed ≤ 10 km/h for 30+ consecutive seconds
 * - Manages 5-minute timeout per question with backend notification on expiry
 * - Pipes timeout notifications to the Offline Buffer
 *
 * Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
 */

import { ContextualQuestionPayload, QuestionResponse } from '@/types';
import { enqueue } from './offlineBuffer';

// --- Constants ---

const MAX_QUEUE_SIZE = 10;
const TIMEOUT_DURATION_MS = 5 * 60 * 1000; // 5 minutes
const DRIVING_SPEED_THRESHOLD_KMH = 10;
const STATIONARY_DURATION_MS = 30 * 1000; // 30 seconds

// --- Types ---

export interface ActiveQuestion {
  payload: ContextualQuestionPayload;
  receivedAt: string; // ISO 8601 UTC
  timeoutTimerId: ReturnType<typeof setTimeout> | null;
}

type QuestionReadyCallback = (question: ContextualQuestionPayload) => void;

// --- State ---

/** Queue of suppressed questions during driving. */
let suppressedQueue: ContextualQuestionPayload[] = [];

/** Currently active/displayed question (if any). */
let activeQuestion: ActiveQuestion | null = null;

/** Callback for when a question is ready to be displayed. */
let questionReadyCallback: QuestionReadyCallback | null = null;

/** Whether the carer is currently considered to be driving. */
let isDriving = false;

/** Timestamp (ms) when speed last dropped to ≤ 10 km/h. */
let stationaryStartMs: number | null = null;

/** Timer for checking stationary duration. */
let stationaryCheckTimerId: ReturnType<typeof setTimeout> | null = null;

// --- GPS Speed Interface ---

/**
 * Current GPS speed in km/h. Updated externally by the GPS tracker service.
 * Defaults to 0 (stationary) when no GPS data is available.
 */
let currentSpeedKmh = 0;

/**
 * Update the current GPS speed. Called by the GPS tracker service
 * whenever a new location fix is obtained.
 */
export function updateGpsSpeed(speedKmh: number): void {
  const previousDriving = isDriving;
  currentSpeedKmh = speedKmh;

  if (speedKmh > DRIVING_SPEED_THRESHOLD_KMH) {
    // Carer is driving
    isDriving = true;
    stationaryStartMs = null;

    if (stationaryCheckTimerId !== null) {
      clearTimeout(stationaryCheckTimerId);
      stationaryCheckTimerId = null;
    }
  } else {
    // Speed is at or below threshold
    if (previousDriving && stationaryStartMs === null) {
      // Just transitioned from driving to slow/stationary
      stationaryStartMs = Date.now();
      scheduleStationaryCheck();
    }
  }
}

/**
 * Get the current GPS speed in km/h.
 */
export function getCurrentSpeed(): number {
  return currentSpeedKmh;
}

// --- Public API ---

/**
 * Register a callback to be invoked when a question is ready to be displayed.
 * The callback receives the question payload.
 */
export function onQuestionReady(callback: QuestionReadyCallback): void {
  questionReadyCallback = callback;
}

/**
 * Main entry point: process an incoming question payload from push notification.
 * If the carer is driving, the question is queued. Otherwise, it is displayed immediately.
 */
export function handleIncomingQuestion(question: ContextualQuestionPayload): void {
  if (isDriving) {
    // Suppress and queue during driving
    if (suppressedQueue.length < MAX_QUEUE_SIZE) {
      suppressedQueue.push(question);
    }
    // If queue is full, discard the question (design constraint: max 10)
    return;
  }

  displayQuestion(question);
}

/**
 * Submit a response to the currently active question.
 * Creates a QuestionResponse and pipes it to the Offline Buffer.
 * Clears the timeout timer for the active question.
 */
export function submitResponse(responseText: string): QuestionResponse | null {
  if (!activeQuestion) return null;

  const response: QuestionResponse = {
    question_id: activeQuestion.payload.id,
    response_text: responseText,
    responded_at: new Date().toISOString(),
  };

  // Clear the timeout timer
  if (activeQuestion.timeoutTimerId !== null) {
    clearTimeout(activeQuestion.timeoutTimerId);
  }

  // Pipe to offline buffer
  enqueue('question_response', response, response.responded_at);

  // Clear active question
  activeQuestion = null;

  return response;
}

/**
 * Dismiss the active question (called when timeout fires or user dismisses).
 */
export function dismissActiveQuestion(): void {
  if (activeQuestion && activeQuestion.timeoutTimerId !== null) {
    clearTimeout(activeQuestion.timeoutTimerId);
  }
  activeQuestion = null;
}

/**
 * Get the currently active question, if any.
 */
export function getActiveQuestion(): ActiveQuestion | null {
  return activeQuestion;
}

/**
 * Get the current suppressed queue (for testing/display purposes).
 */
export function getSuppressedQueue(): ContextualQuestionPayload[] {
  return [...suppressedQueue];
}

/**
 * Check if carer is currently in driving mode.
 */
export function getIsDriving(): boolean {
  return isDriving;
}

// --- Internal Logic ---

/**
 * Display a question to the carer. Sets up the 5-minute timeout.
 */
function displayQuestion(question: ContextualQuestionPayload): void {
  // If there's already an active question, timeout the old one first
  if (activeQuestion) {
    handleTimeout();
  }

  const timeoutTimerId = setTimeout(() => {
    handleTimeout();
  }, TIMEOUT_DURATION_MS);

  activeQuestion = {
    payload: question,
    receivedAt: new Date().toISOString(),
    timeoutTimerId,
  };

  // Notify the UI via callback
  questionReadyCallback?.(question);
}

/**
 * Handle question timeout: dismiss the question and notify backend via offline buffer.
 */
function handleTimeout(): void {
  if (!activeQuestion) return;

  const timeoutPayload = {
    question_id: activeQuestion.payload.id,
    timed_out_at: new Date().toISOString(),
  };

  // Pipe timeout notification to offline buffer
  enqueue('question_response', timeoutPayload, timeoutPayload.timed_out_at);

  // Clear timer (may already be cleared if called from setTimeout)
  if (activeQuestion.timeoutTimerId !== null) {
    clearTimeout(activeQuestion.timeoutTimerId);
  }

  activeQuestion = null;
}

/**
 * Schedule a check for whether the carer has been stationary long enough
 * to release queued questions.
 */
function scheduleStationaryCheck(): void {
  if (stationaryCheckTimerId !== null) {
    clearTimeout(stationaryCheckTimerId);
  }

  stationaryCheckTimerId = setTimeout(() => {
    checkStationaryAndRelease();
  }, STATIONARY_DURATION_MS);
}

/**
 * Check if the carer has been at ≤ 10 km/h for 30+ seconds.
 * If so, release suppressed questions one by one.
 */
function checkStationaryAndRelease(): void {
  stationaryCheckTimerId = null;

  // Confirm still not driving
  if (currentSpeedKmh > DRIVING_SPEED_THRESHOLD_KMH) {
    // Speed went back up, reset
    isDriving = true;
    stationaryStartMs = null;
    return;
  }

  // Confirm 30 seconds have elapsed
  if (stationaryStartMs === null) return;

  const elapsed = Date.now() - stationaryStartMs;
  if (elapsed < STATIONARY_DURATION_MS) {
    // Not enough time yet, reschedule
    scheduleStationaryCheck();
    return;
  }

  // Carer has been stationary for 30+ seconds — release questions
  isDriving = false;
  stationaryStartMs = null;
  releaseQueuedQuestions();
}

/**
 * Release all queued questions one at a time.
 * Displays the first one immediately; the rest remain queued until the
 * active one is answered or times out.
 */
function releaseQueuedQuestions(): void {
  if (suppressedQueue.length === 0) return;

  // Display the first queued question
  const nextQuestion = suppressedQueue.shift();
  if (nextQuestion) {
    displayQuestion(nextQuestion);
  }
}

/**
 * Called after a response is submitted or a question times out,
 * to display the next queued question (if any and not driving).
 */
export function displayNextQueued(): void {
  if (isDriving || suppressedQueue.length === 0) return;

  const nextQuestion = suppressedQueue.shift();
  if (nextQuestion) {
    displayQuestion(nextQuestion);
  }
}

// --- Reset (for testing) ---

export function _resetState(): void {
  suppressedQueue = [];

  if (activeQuestion?.timeoutTimerId !== null) {
    clearTimeout(activeQuestion?.timeoutTimerId ?? undefined);
  }
  activeQuestion = null;
  questionReadyCallback = null;
  isDriving = false;
  stationaryStartMs = null;
  currentSpeedKmh = 0;

  if (stationaryCheckTimerId !== null) {
    clearTimeout(stationaryCheckTimerId);
    stationaryCheckTimerId = null;
  }
}
