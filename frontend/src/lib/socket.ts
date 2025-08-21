import { io, Socket } from 'socket.io-client';

// Socket.IO client configuration
const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || 'http://localhost:8001';

export interface SocketConfig {
  url: string;
  options: {
    transports: string[];
    autoConnect: boolean;
    timeout: number;
    reconnection: boolean;
    reconnectionDelay: number;
    reconnectionAttempts: number;
    forceNew: boolean;
  };
}

const defaultConfig: SocketConfig = {
  url: SOCKET_URL,
  options: {
    transports: ['websocket', 'polling'],
    autoConnect: false,
    timeout: 5000,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 5,
    forceNew: false,
  },
};

// Create socket instance
export const socket: Socket = io(defaultConfig.url, defaultConfig.options);

// Connection state management
export class SocketManager {
  private static instance: SocketManager;
  private socket: Socket;
  private connectionState: 'disconnected' | 'connecting' | 'connected' | 'error' = 'disconnected';
  private listeners: Map<string, Set<(...args: any[]) => void>> = new Map();

  constructor() {
    this.socket = socket;
    this.setupEventListeners();
  }

  static getInstance(): SocketManager {
    if (!SocketManager.instance) {
      SocketManager.instance = new SocketManager();
    }
    return SocketManager.instance;
  }

  private setupEventListeners() {
    this.socket.on('connect', () => {
      this.connectionState = 'connected';
      console.log('🔌 Connected to Socket.IO server');
    });

    this.socket.on('disconnect', (reason: string) => {
      this.connectionState = 'disconnected';
      console.log('❌ Disconnected from Socket.IO server:', reason);
    });

    this.socket.on('connect_error', (error: Error) => {
      this.connectionState = 'error';
      console.error('💥 Socket.IO connection error:', error);
    });

    this.socket.on('reconnect', (attemptNumber: number) => {
      this.connectionState = 'connected';
      console.log(`🔄 Reconnected after ${attemptNumber} attempts`);
    });

    this.socket.on('reconnect_error', (error: Error) => {
      console.error('🔄 Reconnection error:', error);
    });

    this.socket.on('reconnect_failed', () => {
      this.connectionState = 'error';
      console.error('🔄 Reconnection failed after all attempts');
    });
  }

  connect(): void {
    if (this.connectionState !== 'connected') {
      this.connectionState = 'connecting';
      this.socket.connect();
    }
  }

  disconnect(): void {
    if (this.connectionState === 'connected') {
      this.socket.disconnect();
      this.connectionState = 'disconnected';
    }
  }

  getConnectionState(): string {
    return this.connectionState;
  }

  isConnected(): boolean {
    return this.connectionState === 'connected';
  }

  // Event subscription with automatic cleanup
  on(event: string, callback: (...args: any[]) => void): () => void {
    this.socket.on(event, callback);
    
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);

    // Return cleanup function
    return () => {
      this.socket.off(event, callback);
      const eventListeners = this.listeners.get(event);
      if (eventListeners) {
        eventListeners.delete(callback);
        if (eventListeners.size === 0) {
          this.listeners.delete(event);
        }
      }
    };
  }

  // One-time event listener
  once(event: string, callback: (...args: any[]) => void): void {
    this.socket.once(event, callback);
  }

  // Emit event to server
  emit(event: string, data?: any): void {
    if (this.isConnected()) {
      this.socket.emit(event, data);
    } else {
      console.warn(`Cannot emit "${event}" - socket not connected`);
    }
  }

  // Emit with acknowledgment
  emitWithAck(event: string, data?: any): Promise<any> {
    return new Promise((resolve, reject) => {
      if (this.isConnected()) {
        this.socket.emit(event, data, (response: any) => {
          if (response.error) {
            reject(new Error(response.error));
          } else {
            resolve(response);
          }
        });
      } else {
        reject(new Error('Socket not connected'));
      }
    });
  }

  // Clean up all listeners
  cleanup(): void {
    this.listeners.forEach((callbacks, event) => {
      callbacks.forEach(callback => {
        this.socket.off(event, callback);
      });
    });
    this.listeners.clear();
  }
}

// Export singleton instance
export const socketManager = SocketManager.getInstance();

// Trading-specific event types
export interface TradingEvents {
  // Position updates
  'position_update': {
    symbol: string;
    quantity: number;
    avg_price: number;
    pnl: number;
    unrealized_pnl: number;
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
  };

  // Order updates
  'order_update': {
    order_id: string;
    status: string;
    filled_qty: number;
    price: number;
    timestamp: string;
  };

  // Market data updates
  'market_data': {
    symbol: string;
    ltp: number;
    bid: number;
    ask: number;
    volume: number;
    oi: number;
    timestamp: string;
  };

  // Strategy updates
  'strategy_update': {
    strategy_id: string;
    status: string;
    pnl: number;
    trades_count: number;
    win_rate: number;
    max_drawdown: number;
  };

  // Risk alerts
  'risk_alert': {
    type: 'position_limit' | 'daily_loss' | 'circuit_breaker' | 'margin';
    message: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    timestamp: string;
  };

  // System notifications
  'system_notification': {
    type: 'info' | 'warning' | 'error' | 'success';
    message: string;
    timestamp: string;
  };
}

// Type-safe event helpers
export const TradingSocket = {
  onPositionUpdate: (callback: (data: TradingEvents['position_update']) => void) => 
    socketManager.on('position_update', callback),
  
  onOrderUpdate: (callback: (data: TradingEvents['order_update']) => void) => 
    socketManager.on('order_update', callback),
  
  onMarketData: (callback: (data: TradingEvents['market_data']) => void) => 
    socketManager.on('market_data', callback),
  
  onStrategyUpdate: (callback: (data: TradingEvents['strategy_update']) => void) => 
    socketManager.on('strategy_update', callback),
  
  onRiskAlert: (callback: (data: TradingEvents['risk_alert']) => void) => 
    socketManager.on('risk_alert', callback),
  
  onSystemNotification: (callback: (data: TradingEvents['system_notification']) => void) => 
    socketManager.on('system_notification', callback),
};

export default socketManager; 