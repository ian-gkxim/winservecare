import { useCallback, useEffect, useRef, useState } from 'react';

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  autoConnect?: boolean;
  maxReconnectAttempts?: number;
}

export interface UseWebSocketReturn {
  connectionState: ConnectionState;
  connect: () => void;
  disconnect: () => void;
  send: (data: unknown) => void;
}

export function useWebSocket({
  url,
  onMessage,
  autoConnect = false,
  maxReconnectAttempts = 3,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  const intentionalCloseRef = useRef(false);

  // Keep onMessage ref in sync to avoid stale closures
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      setConnectionState('error');
      return;
    }

    const delay = Math.pow(2, reconnectAttemptsRef.current) * 1000; // 1s, 2s, 4s
    reconnectAttemptsRef.current += 1;

    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [maxReconnectAttempts]);

  const connect = useCallback(() => {
    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    intentionalCloseRef.current = false;
    setConnectionState('connecting');

    // Build the WebSocket URL
    const wsUrl = url.startsWith('ws://') || url.startsWith('wss://')
      ? url
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${url}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnectionState('connected');
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch {
        // If not JSON, pass raw data
        onMessageRef.current(event.data);
      }
    };

    ws.onerror = () => {
      setConnectionState('error');
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (!intentionalCloseRef.current) {
        setConnectionState('disconnected');
        scheduleReconnect();
      } else {
        setConnectionState('disconnected');
      }
    };

    wsRef.current = ws;
  }, [url, scheduleReconnect]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    reconnectAttemptsRef.current = 0;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnectionState('disconnected');
  }, [clearReconnectTimer]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  // Auto-connect on mount if requested
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      intentionalCloseRef.current = true;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [autoConnect, connect, clearReconnectTimer]);

  return { connectionState, connect, disconnect, send };
}
