import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from './useWebSocket';

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
    if (this.onclose) this.onclose();
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

  simulateError() {
    if (this.onerror) this.onerror();
  }

  simulateClose() {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose();
  }
}

describe('useWebSocket', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('starts in disconnected state', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage })
    );
    expect(result.current.connectionState).toBe('disconnected');
  });

  it('transitions to connecting then connected on connect', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage })
    );

    act(() => {
      result.current.connect();
    });

    expect(result.current.connectionState).toBe('connecting');

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    expect(result.current.connectionState).toBe('connected');
  });

  it('calls onMessage when receiving data', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage })
    );

    act(() => {
      result.current.connect();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      MockWebSocket.instances[0].simulateMessage({ type: 'progress', step: 1 });
    });

    expect(onMessage).toHaveBeenCalledWith({ type: 'progress', step: 1 });
  });

  it('sends JSON data through WebSocket', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage })
    );

    act(() => {
      result.current.connect();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      result.current.send({ type: 'start' });
    });

    expect(MockWebSocket.instances[0].send).toHaveBeenCalledWith(JSON.stringify({ type: 'start' }));
  });

  it('disconnects and returns to disconnected state', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage })
    );

    act(() => {
      result.current.connect();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      result.current.disconnect();
    });

    expect(result.current.connectionState).toBe('disconnected');
  });

  it('attempts auto-reconnect with exponential backoff on unexpected close', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage, maxReconnectAttempts: 3 })
    );

    act(() => {
      result.current.connect();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    // Simulate unexpected close
    act(() => {
      MockWebSocket.instances[0].simulateClose();
    });

    expect(result.current.connectionState).toBe('disconnected');

    // After 1s (first backoff), should try to reconnect
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // A new WebSocket instance should be created
    expect(MockWebSocket.instances.length).toBe(2);
  });

  it('sets error state after max reconnect attempts', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage, maxReconnectAttempts: 3 })
    );

    act(() => {
      result.current.connect();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    // Simulate 3 unexpected closes with backoff
    act(() => {
      MockWebSocket.instances[0].simulateClose(); // attempt 1 scheduled
    });
    act(() => {
      vi.advanceTimersByTime(1000); // reconnect attempt 1
    });
    act(() => {
      MockWebSocket.instances[1].simulateClose(); // attempt 2 scheduled
    });
    act(() => {
      vi.advanceTimersByTime(2000); // reconnect attempt 2
    });
    act(() => {
      MockWebSocket.instances[2].simulateClose(); // attempt 3 scheduled
    });
    act(() => {
      vi.advanceTimersByTime(4000); // reconnect attempt 3
    });
    act(() => {
      MockWebSocket.instances[3].simulateClose(); // no more attempts
    });

    expect(result.current.connectionState).toBe('error');
  });

  it('does not reconnect after intentional disconnect', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage })
    );

    act(() => {
      result.current.connect();
    });
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    act(() => {
      result.current.disconnect();
    });

    // Advance timers - should not reconnect
    act(() => {
      vi.advanceTimersByTime(10000);
    });

    expect(MockWebSocket.instances.length).toBe(1);
    expect(result.current.connectionState).toBe('disconnected');
  });

  it('builds correct WebSocket URL for relative paths', () => {
    const onMessage = vi.fn();

    // Mock window.location
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:5173' },
      writable: true,
    });

    const { result } = renderHook(() =>
      useWebSocket({ url: '/ws/optimise', onMessage })
    );

    act(() => {
      result.current.connect();
    });

    expect(MockWebSocket.instances[0].url).toBe('ws://localhost:5173/ws/optimise');
  });
});
