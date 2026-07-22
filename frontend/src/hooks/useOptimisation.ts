import { useCallback, useMemo, useState } from 'react';
import { useWebSocket } from './useWebSocket';
import type {
  AnimationStep,
  Route,
  WsServerMessage,
} from '../types';
import type { ConnectionState } from './useWebSocket';

export interface SolverProgressState {
  phase: 'idle' | 'distance_matrix' | 'solver';
  elapsedSeconds: number;
  timeLimitSeconds: number;
  percentageComplete: number;
  solutionsFound: number;
  currentBestScore: number | null;
  distanceMatrixStatus: 'idle' | 'in_progress' | 'complete' | 'failed';
  totalPairs: number;
}

export interface OptimisationState {
  isRunning: boolean;
  isPaused: boolean;
  currentStep: number;
  steps: AnimationStep[];
  progress: number;
  result: { finalScore: number; routes: Route[] } | null;
  error: { step: number; message: string } | null;
  connectionState: ConnectionState;
  solverProgress: SolverProgressState;
}

export interface UseOptimisationReturn extends OptimisationState {
  startOptimisation: (visitIds?: number[], targetDate?: string) => void;
  pause: () => void;
  resume: () => void;
  disconnect: () => void;
}

export function useOptimisation(): UseOptimisationReturn {
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [steps, setSteps] = useState<AnimationStep[]>([]);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ finalScore: number; routes: Route[] } | null>(null);
  const [error, setError] = useState<{ step: number; message: string } | null>(null);
  const [solverProgress, setSolverProgress] = useState<SolverProgressState>({
    phase: 'idle',
    elapsedSeconds: 0,
    timeLimitSeconds: 10,
    percentageComplete: 0,
    solutionsFound: 0,
    currentBestScore: null,
    distanceMatrixStatus: 'idle',
    totalPairs: 0,
  });

  const handleMessage = useCallback((data: unknown) => {
    const message = data as WsServerMessage;

    switch (message.type) {
      case 'step':
        setSteps((prev) => [...prev, message.payload]);
        break;

      case 'progress':
        setCurrentStep(message.step);
        setProgress(message.score);
        break;

      case 'solver_progress':
        if (message.phase === 'distance_matrix') {
          setSolverProgress((prev) => ({
            ...prev,
            phase: 'distance_matrix',
            elapsedSeconds: message.elapsed_seconds,
            totalPairs: message.total_pairs ?? prev.totalPairs,
            distanceMatrixStatus: message.status ?? 'in_progress',
          }));
        } else if (message.phase === 'solver') {
          setSolverProgress((prev) => ({
            ...prev,
            phase: 'solver',
            elapsedSeconds: message.elapsed_seconds,
            timeLimitSeconds: message.time_limit_seconds ?? prev.timeLimitSeconds,
            percentageComplete: message.percentage_complete ?? prev.percentageComplete,
            solutionsFound: message.solutions_found ?? prev.solutionsFound,
            currentBestScore: message.current_best_score ?? prev.currentBestScore,
          }));
        }
        break;

      case 'complete':
        setResult({ finalScore: message.finalScore, routes: message.routes });
        setSolverProgress((prev) => ({ ...prev, phase: 'idle', percentageComplete: 100 }));
        setIsRunning(false);
        setIsPaused(false);
        break;

      case 'error':
        setError({ step: message.step, message: message.message });
        setSolverProgress((prev) => ({ ...prev, phase: 'idle' }));
        setIsRunning(false);
        setIsPaused(false);
        break;

      case 'deprecation_notice':
        // Silently acknowledge — no UI action needed
        break;
    }
  }, []);

  const { connectionState, connect, disconnect, send } = useWebSocket({
    url: '/ainative/ws/optimise',
    onMessage: handleMessage,
  });

  const startOptimisation = useCallback(
    (visitIds?: number[], targetDate?: string) => {
      // Reset state
      setIsRunning(true);
      setIsPaused(false);
      setCurrentStep(0);
      setSteps([]);
      setProgress(0);
      setResult(null);
      setError(null);
      setSolverProgress({
        phase: 'idle',
        elapsedSeconds: 0,
        timeLimitSeconds: 10,
        percentageComplete: 0,
        solutionsFound: 0,
        currentBestScore: null,
        distanceMatrixStatus: 'idle',
        totalPairs: 0,
      });

      // Connect and send start message
      connect();

      // Small delay to allow WebSocket to open before sending
      const sendStart = () => {
        send({ type: 'start', visitIds, targetDate });
      };

      // If already connected, send immediately; otherwise wait for open
      setTimeout(sendStart, 100);
    },
    [connect, send]
  );

  const pause = useCallback(() => {
    send({ type: 'pause' });
    setIsPaused(true);
  }, [send]);

  const resume = useCallback(() => {
    send({ type: 'resume' });
    setIsPaused(false);
  }, [send]);

  return useMemo(
    () => ({
      isRunning,
      isPaused,
      currentStep,
      steps,
      progress,
      result,
      error,
      connectionState,
      solverProgress,
      startOptimisation,
      pause,
      resume,
      disconnect,
    }),
    [
      isRunning,
      isPaused,
      currentStep,
      steps,
      progress,
      result,
      error,
      connectionState,
      solverProgress,
      startOptimisation,
      pause,
      resume,
      disconnect,
    ]
  );
}
