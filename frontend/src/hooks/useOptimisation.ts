import { useCallback, useMemo, useState } from 'react';
import { useWebSocket } from './useWebSocket';
import type {
  AnimationStep,
  Route,
  WsServerMessage,
} from '../types';
import type { ConnectionState } from './useWebSocket';

export interface OptimisationState {
  isRunning: boolean;
  isPaused: boolean;
  currentStep: number;
  steps: AnimationStep[];
  progress: number;
  result: { finalScore: number; routes: Route[] } | null;
  error: { step: number; message: string } | null;
  connectionState: ConnectionState;
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

      case 'complete':
        setResult({ finalScore: message.finalScore, routes: message.routes });
        setIsRunning(false);
        setIsPaused(false);
        break;

      case 'error':
        setError({ step: message.step, message: message.message });
        setIsRunning(false);
        setIsPaused(false);
        break;
    }
  }, []);

  const { connectionState, connect, disconnect, send } = useWebSocket({
    url: '/ws/optimise',
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
      startOptimisation,
      pause,
      resume,
      disconnect,
    ]
  );
}
