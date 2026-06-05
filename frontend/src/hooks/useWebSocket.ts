import { useEffect, useRef, useState, useCallback } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

type MessageHandler = (data: Record<string, unknown>) => void;
type HandlerMap = Record<string, MessageHandler>;

interface UseWebSocketReturn {
  connected: boolean;
  sendMessage: (payload: Record<string, unknown>) => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const RECONNECT_DELAY_MS = 3000;

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Auto-reconnecting WebSocket hook.
 *
 * @param url      - WebSocket URL (e.g. '/stream' or 'ws://...')
 * @param handlers - Map from message `type` string to handler callback.
 *
 * The hook:
 *   - Opens a WebSocket on mount.
 *   - On each incoming message, parses JSON and dispatches to `handlers[data.type]`.
 *   - On close or error, schedules a reconnect after RECONNECT_DELAY_MS.
 *   - Cleans up the WebSocket and pending timer on unmount.
 */
export function useWebSocket(url: string, handlers: HandlerMap): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const handlersRef = useRef<HandlerMap>(handlers);
  const [connected, setConnected] = useState(false);

  // Keep handlersRef current so callbacks always use the latest closures
  // without triggering reconnection when handlers reference changes.
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    // Resolve the URL: convert path-only URLs to full ws:// URLs
    let wsUrl = url;
    if (url.startsWith('/')) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${protocol}//${window.location.host}${url}`;
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      setConnected(true);
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>;
        const type = data.type as string | undefined;
        if (type && Object.prototype.hasOwnProperty.call(handlersRef.current, type)) {
          handlersRef.current[type](data);
        }
      } catch {
        // Non-JSON frames are silently ignored
      }
    };

    ws.onerror = () => {
      // Let onclose handle reconnection
      ws.close();
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      setConnected(false);
      wsRef.current = null;
      // Schedule reconnect
      reconnectTimerRef.current = setTimeout(() => {
        if (isMountedRef.current) connect();
      }, RECONNECT_DELAY_MS);
    };
  }, [url]);

  // Initial connection
  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect loop on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Sends a JSON-serialised payload through the WebSocket if the connection is open.
   */
  const sendMessage = useCallback((payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  return { connected, sendMessage };
}
