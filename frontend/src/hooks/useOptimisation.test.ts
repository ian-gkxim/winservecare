import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useOptimisation } from './useOptimisation';

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn(() => {
    this.readyState = WebSocket.CLOSED;
  });
  send = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  simulateOpen() {
    this.readyState = WebSocket.OPEN;
    if (this.onopen) this.onopen();
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) });
  }
}

describe('useOptimisation', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('starts with default state', () => {
    const { result } = renderHook(() => useOptimisation());

    expect(result.current.isRunning).toBe(false);
    expect(result.current.isPaused).toBe(false);
    expect(result.current.currentStep).toBe(0);
    expect(result.current.steps).toEqual([]);
    expect(result.current.progress).toBe(0);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('startOptimisation sets isRunning and resets state', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation();
    });

    expect(result.current.isRunning).toBe(true);
    expect(result.current.isPaused).toBe(false);
    expect(result.current.steps).toEqual([]);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('handles step messages by appending to steps array', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    const stepPayload = {
      stepNumber: 1,
      stepName: 'Plot Locations',
      data: { type: 'locations', carers: [], patients: [] },
    };

    act(() => {
      MockWebSocket.instances[0].simulateMessage({ type: 'step', payload: stepPayload });
    });

    expect(result.current.steps).toHaveLength(1);
    expect(result.current.steps[0]).toEqual(stepPayload);
  });

  it('handles progress messages by updating currentStep and progress', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'progress',
        step: 3,
        name: 'Assigning',
        score: 42.5,
      });
    });

    expect(result.current.currentStep).toBe(3);
    expect(result.current.progress).toBe(42.5);
  });

  it('handles complete messages by setting result and stopping', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    const routes = [{ carerId: 1, stops: [], totalTravelMinutes: 30, totalMileage: 10, totalCost: 5 }];

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'complete',
        finalScore: 85.2,
        routes,
      });
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.result).toEqual({ finalScore: 85.2, routes });
  });

  it('handles error messages by setting error and stopping', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'error',
        step: 2,
        message: 'Google Maps API unavailable',
      });
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.error).toEqual({ step: 2, message: 'Google Maps API unavailable' });
  });

  it('pause sends pause message and sets isPaused', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      result.current.pause();
    });

    expect(result.current.isPaused).toBe(true);
    expect(MockWebSocket.instances[0].send).toHaveBeenCalledWith(JSON.stringify({ type: 'pause' }));
  });

  it('resume sends resume message and clears isPaused', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      result.current.pause();
    });
    act(() => {
      result.current.resume();
    });

    expect(result.current.isPaused).toBe(false);
    expect(MockWebSocket.instances[0].send).toHaveBeenCalledWith(JSON.stringify({ type: 'resume' }));
  });

  it('sends start message with visitIds when provided', () => {
    const { result } = renderHook(() => useOptimisation());

    act(() => {
      result.current.startOptimisation([1, 2, 3]);
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    // After timeout, start message should be sent
    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(MockWebSocket.instances[0].send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'start', visitIds: [1, 2, 3] })
    );
  });
});
