import { useEffect, useRef } from 'react';
import { socketManager, TradingSocket } from '../lib/socket';
import { useAppActions } from '../stores/useAppStore';

export const useRealtime = () => {
  const actions = useAppActions();
  const cleanupFunctions = useRef<(() => void)[]>([]);

  useEffect(() => {
    // Connect to socket
    socketManager.connect();

    // Set up event listeners
    const cleanup: (() => void)[] = [];

    // Connection status
    const onConnect = () => {
      actions.setConnected(true);
      actions.updateSystemStatus({ socket_connected: true });
    };

    const onDisconnect = () => {
      actions.setConnected(false);
      actions.updateSystemStatus({ socket_connected: false });
    };

    cleanup.push(socketManager.on('connect', onConnect));
    cleanup.push(socketManager.on('disconnect', onDisconnect));

    // Position updates
    cleanup.push(
      TradingSocket.onPositionUpdate((data) => {
        actions.updatePosition({
          symbol: data.symbol,
          quantity: data.quantity,
          avg_price: data.avg_price,
          current_price: data.avg_price, // Will be updated by market data
          pnl: data.pnl,
          unrealized_pnl: data.unrealized_pnl,
          delta: data.delta,
          gamma: data.gamma,
          theta: data.theta,
          vega: data.vega,
          entry_time: new Date().toISOString(),
          strategy_id: 'default',
        });
      })
    );

    // Order updates
    cleanup.push(
      TradingSocket.onOrderUpdate((data) => {
        actions.updateOrder({
          order_id: data.order_id,
          symbol: 'NIFTY', // Will be provided by backend
          side: 'BUY', // Will be provided by backend
          quantity: data.filled_qty,
          price: data.price,
          filled_qty: data.filled_qty,
          status: data.status as 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED',
          timestamp: data.timestamp,
          strategy_id: 'default',
        });
      })
    );

    // Market data updates
    cleanup.push(
      TradingSocket.onMarketData((data) => {
        actions.updateMarketData(data.symbol, {
          symbol: data.symbol,
          ltp: data.ltp,
          bid: data.bid,
          ask: data.ask,
          volume: data.volume,
          oi: data.oi,
          change: 0, // Calculate from previous LTP
          change_percent: 0, // Calculate from previous LTP
          timestamp: data.timestamp,
        });
      })
    );

    // Strategy updates
    cleanup.push(
      TradingSocket.onStrategyUpdate((data) => {
        actions.updateStrategy({
          strategy_id: data.strategy_id,
          name: data.strategy_id, // Backend should provide name
          status: data.status as 'ACTIVE' | 'INACTIVE' | 'PAUSED',
          pnl: data.pnl,
          trades_count: data.trades_count,
          win_rate: data.win_rate,
          max_drawdown: data.max_drawdown,
          profit_factor: 0, // Calculate from trades
          sharpe_ratio: 0, // Calculate from returns
          last_updated: new Date().toISOString(),
        });
      })
    );

    // Risk alerts
    cleanup.push(
      TradingSocket.onRiskAlert((data) => {
        actions.addAlert({
          id: `${Date.now()}-${Math.random()}`,
          type: data.type,
          message: data.message,
          severity: data.severity,
          timestamp: data.timestamp,
          acknowledged: false,
        });
      })
    );

    // System notifications
    cleanup.push(
      TradingSocket.onSystemNotification((data) => {
        actions.addAlert({
          id: `${Date.now()}-${Math.random()}`,
          type: 'system',
          message: data.message,
          severity: data.type === 'error' ? 'high' : 'medium',
          timestamp: data.timestamp,
          acknowledged: false,
        });
      })
    );

    cleanupFunctions.current = cleanup;

    return () => {
      cleanup.forEach(fn => fn());
      socketManager.disconnect();
    };
  }, []); // Remove actions dependency to prevent infinite loop

  // Return socket manager for direct access if needed
  return {
    socketManager,
    emit: socketManager.emit.bind(socketManager),
    emitWithAck: socketManager.emitWithAck.bind(socketManager),
    isConnected: socketManager.isConnected(),
    connectionState: socketManager.getConnectionState(),
  };
};

// Specific hooks for different data types
export const usePositionUpdates = () => {
  const actions = useAppActions();
  
  useEffect(() => {
    const cleanup = TradingSocket.onPositionUpdate((data) => {
      actions.updatePosition({
        symbol: data.symbol,
        quantity: data.quantity,
        avg_price: data.avg_price,
        current_price: data.avg_price,
        pnl: data.pnl,
        unrealized_pnl: data.unrealized_pnl,
        delta: data.delta,
        gamma: data.gamma,
        theta: data.theta,
        vega: data.vega,
        entry_time: new Date().toISOString(),
        strategy_id: 'default',
      });
    });

    return cleanup;
  }, []); // Remove actions dependency to prevent infinite loop
};

export const useOrderUpdates = () => {
  const actions = useAppActions();
  
  useEffect(() => {
    const cleanup = TradingSocket.onOrderUpdate((data) => {
      actions.updateOrder({
        order_id: data.order_id,
        symbol: 'NIFTY',
        side: 'BUY',
        quantity: data.filled_qty,
        price: data.price,
        filled_qty: data.filled_qty,
        status: data.status as 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED',
        timestamp: data.timestamp,
        strategy_id: 'default',
      });
    });

    return cleanup;
  }, []); // Remove actions dependency to prevent infinite loop
};

export const useMarketDataUpdates = () => {
  const actions = useAppActions();
  
  useEffect(() => {
    const cleanup = TradingSocket.onMarketData((data) => {
      actions.updateMarketData(data.symbol, {
        symbol: data.symbol,
        ltp: data.ltp,
        bid: data.bid,
        ask: data.ask,
        volume: data.volume,
        oi: data.oi,
        change: 0,
        change_percent: 0,
        timestamp: data.timestamp,
      });
    });

    return cleanup;
  }, []); // Remove actions dependency to prevent infinite loop
};

export const useRiskAlerts = () => {
  const actions = useAppActions();
  
  useEffect(() => {
    const cleanup = TradingSocket.onRiskAlert((data) => {
      actions.addAlert({
        id: `${Date.now()}-${Math.random()}`,
        type: data.type,
        message: data.message,
        severity: data.severity,
        timestamp: data.timestamp,
        acknowledged: false,
      });
    });

    return cleanup;
  }, []); // Remove actions dependency to prevent infinite loop
};

export default useRealtime; 