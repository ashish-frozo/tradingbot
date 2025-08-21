import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

// Type definitions
export interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  pnl: number;
  unrealized_pnl: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  entry_time: string;
  exit_time?: string;
  strategy_id: string;
}

export interface Order {
  order_id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  filled_qty: number;
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED';
  timestamp: string;
  strategy_id: string;
}

export interface Strategy {
  strategy_id: string;
  name: string;
  status: 'ACTIVE' | 'INACTIVE' | 'PAUSED';
  pnl: number;
  trades_count: number;
  win_rate: number;
  max_drawdown: number;
  profit_factor: number;
  sharpe_ratio: number;
  last_updated: string;
}

export interface MarketData {
  symbol: string;
  ltp: number;
  bid: number;
  ask: number;
  volume: number;
  oi: number;
  change: number;
  change_percent: number;
  timestamp: string;
}

export interface RiskMetrics {
  total_pnl: number;
  daily_pnl: number;
  margin_used: number;
  margin_available: number;
  position_count: number;
  max_position_limit: number;
  circuit_breaker_status: boolean;
  vix_level: number;
  daily_loss_limit: number;
  current_drawdown: number;
}

export interface Alert {
  id: string;
  type: 'position_limit' | 'daily_loss' | 'circuit_breaker' | 'margin' | 'system';
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
  acknowledged: boolean;
}

export interface SystemStatus {
  backend_connected: boolean;
  socket_connected: boolean;
  broker_connected: boolean;
  market_data_status: 'live' | 'delayed' | 'disconnected';
  last_heartbeat: string;
  latency: number;
  server_time: string;
}

// Store interface
interface AppStore {
  // Connection state
  isConnected: boolean;
  systemStatus: SystemStatus;
  
  // Trading data
  positions: Position[];
  orders: Order[];
  strategies: Strategy[];
  marketData: Map<string, MarketData>;
  riskMetrics: RiskMetrics;
  
  // UI state
  alerts: Alert[];
  selectedStrategy: string | null;
  darkMode: boolean;
  sidebarCollapsed: boolean;
  
  // Historical data for charts
  equityCurve: Array<{ timestamp: string; value: number }>;
  latencyHistory: number[];
  
  // Actions
  setConnected: (connected: boolean) => void;
  updateSystemStatus: (status: Partial<SystemStatus>) => void;
  
  // Position actions
  setPositions: (positions: Position[]) => void;
  updatePosition: (position: Position) => void;
  removePosition: (symbol: string) => void;
  
  // Order actions
  setOrders: (orders: Order[]) => void;
  updateOrder: (order: Order) => void;
  addOrder: (order: Order) => void;
  
  // Strategy actions
  setStrategies: (strategies: Strategy[]) => void;
  updateStrategy: (strategy: Strategy) => void;
  setSelectedStrategy: (strategyId: string | null) => void;
  
  // Market data actions
  updateMarketData: (symbol: string, data: MarketData) => void;
  
  // Risk metrics actions
  updateRiskMetrics: (metrics: RiskMetrics) => void;
  
  // Alert actions
  addAlert: (alert: Alert) => void;
  acknowledgeAlert: (alertId: string) => void;
  clearAlerts: () => void;
  
  // UI actions
  toggleDarkMode: () => void;
  toggleSidebar: () => void;
  
  // Chart data actions
  updateEquityCurve: (point: { timestamp: string; value: number }) => void;
  updateLatencyHistory: (latency: number) => void;
  
  // Emergency actions
  killAllPositions: () => void;
  
            // Mock data generation for testing
  generateMockEquityData: () => void;
  generateMockPositions: () => void;
  generateMockStrategies: () => void;
}

// Initial state
const initialState = {
  isConnected: false,
  systemStatus: {
    backend_connected: false,
    socket_connected: false,
    broker_connected: false,
    market_data_status: 'disconnected' as const,
    last_heartbeat: '',
    latency: 0,
    server_time: '',
  },
  positions: [],
  orders: [],
  strategies: [],
  marketData: new Map(),
  riskMetrics: {
    total_pnl: 45250,
    daily_pnl: 8750,
    margin_used: 125000,
    margin_available: 375000,
    position_count: 8,
    max_position_limit: 100,
    circuit_breaker_status: false,
    vix_level: 18.5,
    daily_loss_limit: 25000,
    current_drawdown: 0.05,
  },
  alerts: [],
  selectedStrategy: null,
  darkMode: false,
  sidebarCollapsed: false,
  equityCurve: [],
  latencyHistory: [45, 52, 38, 67, 89, 43, 71, 56, 92, 48, 63, 85, 41, 77, 59, 94, 46, 68, 82, 51, 73, 87, 44, 69, 91, 47, 65, 83, 49, 76],
};

// Create store
export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      immer((set) => ({
        ...initialState,
        
        // Connection actions
        setConnected: (connected) => set({ isConnected: connected }),
        updateSystemStatus: (status) => set((state) => {
          Object.assign(state.systemStatus, status);
        }),
        
        // Position actions
        setPositions: (positions) => set({ positions }),
        updatePosition: (position) => set((state) => {
          const index = state.positions.findIndex(p => p.symbol === position.symbol);
          if (index >= 0) {
            state.positions[index] = position;
          } else {
            state.positions.push(position);
          }
        }),
        removePosition: (symbol) => set((state) => {
          state.positions = state.positions.filter(p => p.symbol !== symbol);
        }),
        
        // Order actions
        setOrders: (orders) => set({ orders }),
        updateOrder: (order) => set((state) => {
          const index = state.orders.findIndex(o => o.order_id === order.order_id);
          if (index >= 0) {
            state.orders[index] = order;
          } else {
            state.orders.push(order);
          }
        }),
        addOrder: (order) => set((state) => {
          state.orders.push(order);
        }),
        
        // Strategy actions
        setStrategies: (strategies) => set({ strategies }),
        updateStrategy: (strategy) => set((state) => {
          const index = state.strategies.findIndex(s => s.strategy_id === strategy.strategy_id);
          if (index >= 0) {
            state.strategies[index] = strategy;
          } else {
            state.strategies.push(strategy);
          }
        }),
        setSelectedStrategy: (strategyId) => set({ selectedStrategy: strategyId }),
        
        // Market data actions
        updateMarketData: (symbol, data) => set((state) => {
          state.marketData.set(symbol, data);
        }),
        
        // Risk metrics actions
        updateRiskMetrics: (metrics) => set({ riskMetrics: metrics }),
        
        // Alert actions
        addAlert: (alert) => set((state) => {
          state.alerts.push(alert);
          // Keep only last 100 alerts
          if (state.alerts.length > 100) {
            state.alerts = state.alerts.slice(-100);
          }
        }),
        acknowledgeAlert: (alertId) => set((state) => {
          const alert = state.alerts.find(a => a.id === alertId);
          if (alert) {
            alert.acknowledged = true;
          }
        }),
        clearAlerts: () => set({ alerts: [] }),
        
        // UI actions
        toggleDarkMode: () => set((state) => {
          state.darkMode = !state.darkMode;
        }),
        toggleSidebar: () => set((state) => {
          state.sidebarCollapsed = !state.sidebarCollapsed;
        }),
        
        // Chart data actions
        updateEquityCurve: (point) => set((state) => {
          state.equityCurve.push(point);
          // Keep only last 1000 points
          if (state.equityCurve.length > 1000) {
            state.equityCurve = state.equityCurve.slice(-1000);
          }
        }),
        updateLatencyHistory: (latency) => set((state) => {
          state.latencyHistory.push(latency);
          // Keep only last 100 latency measurements
          if (state.latencyHistory.length > 100) {
            state.latencyHistory = state.latencyHistory.slice(-100);
          }
        }),
        
        // Emergency actions
        killAllPositions: () => {
          // This would trigger the emergency kill switch
          // Implementation would emit socket event to backend
          console.log('🚨 Emergency kill switch activated!');
        },
        
        // Mock data generation for testing
        generateMockEquityData: () => set((state) => {
          const now = Date.now();
          const startValue = 1000000; // Starting with 10 lakh
          const dataPoints: Array<{ timestamp: string; value: number }> = [];
          
          for (let i = 0; i < 50; i++) {
            const timestamp = new Date(now - (49 - i) * 30000); // 30 seconds apart
            const randomChange = (Math.random() - 0.5) * 10000; // Random change up to ±5000
            const value: number = i === 0 ? startValue : dataPoints[i - 1].value + randomChange;
            
            dataPoints.push({
              timestamp: timestamp.toISOString(),
              value: Math.max(value, startValue * 0.8), // Don't go below 80% of start value
            });
          }
          
          state.equityCurve = dataPoints;
        }),
        
        // Generate mock position data for testing
        generateMockPositions: () => set((state) => {
          const mockPositions: Position[] = [
            {
              symbol: 'NIFTY50_25DEC_24350_CE',
              quantity: 10,
              avg_price: 125.50,
              current_price: 132.75,
              pnl: 725,
              unrealized_pnl: 725,
              delta: 0.45,
              gamma: 0.008,
              theta: -15.5,
              vega: 28.2,
              entry_time: new Date(Date.now() - 4 * 60 * 1000).toISOString(), // 4 minutes ago
              strategy_id: 'vol_oi_strategy',
            },
            {
              symbol: 'NIFTY50_25DEC_24300_PE',
              quantity: -5,
              avg_price: 89.25,
              current_price: 76.50,
              pnl: 638,
              unrealized_pnl: 638,
              delta: -0.32,
              gamma: 0.006,
              theta: -12.8,
              vega: 22.1,
              entry_time: new Date(Date.now() - 7 * 60 * 1000).toISOString(), // 7 minutes ago
              strategy_id: 'vol_oi_strategy',
            },
            {
              symbol: 'NIFTY50_25DEC_24400_CE',
              quantity: 15,
              avg_price: 78.90,
              current_price: 65.25,
              pnl: -2048,
              unrealized_pnl: -2048,
              delta: 0.28,
              gamma: 0.005,
              theta: -18.2,
              vega: 31.5,
              entry_time: new Date(Date.now() - 8 * 60 * 1000).toISOString(), // 8 minutes ago
              strategy_id: 'vol_oi_strategy',
            },
          ];
          
          state.positions = mockPositions;
        }),
        
        // Generate mock strategy data for testing
        generateMockStrategies: () => set((state) => {
          const mockStrategies: Strategy[] = [
            {
              strategy_id: 'vol_oi_strategy',
              name: 'Volume-OI Confirm',
              status: 'ACTIVE',
              pnl: 45250,
              trades_count: 47,
              win_rate: 72.3,
              max_drawdown: 8.5,
              profit_factor: 2.1,
              sharpe_ratio: 1.8,
              last_updated: new Date().toISOString(),
            },
            {
              strategy_id: 'mean_reversion',
              name: 'Mean Reversion',
              status: 'PAUSED',
              pnl: -12350,
              trades_count: 23,
              win_rate: 43.5,
              max_drawdown: 15.2,
              profit_factor: 0.8,
              sharpe_ratio: -0.3,
              last_updated: new Date().toISOString(),
            },
            {
              strategy_id: 'momentum_breakout',
              name: 'Momentum Breakout',
              status: 'ACTIVE',
              pnl: 78900,
              trades_count: 65,
              win_rate: 65.4,
              max_drawdown: 12.8,
              profit_factor: 1.7,
              sharpe_ratio: 1.4,
              last_updated: new Date().toISOString(),
            },
            {
              strategy_id: 'gamma_scalp',
              name: 'Gamma Scalping',
              status: 'INACTIVE',
              pnl: 23450,
              trades_count: 156,
              win_rate: 58.9,
              max_drawdown: 6.2,
              profit_factor: 1.3,
              sharpe_ratio: 0.9,
              last_updated: new Date().toISOString(),
            },
          ];
          
          state.strategies = mockStrategies;
        }),
      })),
      {
        name: 'trading-app-storage',
        partialize: (state) => ({
          darkMode: state.darkMode,
          sidebarCollapsed: state.sidebarCollapsed,
          selectedStrategy: state.selectedStrategy,
        }),
      }
    ),
    {
      name: 'trading-app-store',
    }
  )
);

// Selector hooks for better performance
export const usePositions = () => useAppStore(state => state.positions);
export const useOrders = () => useAppStore(state => state.orders);
export const useStrategies = () => useAppStore(state => state.strategies);
export const useRiskMetrics = () => useAppStore(state => state.riskMetrics);
export const useAlerts = () => useAppStore(state => state.alerts);
export const useSystemStatus = () => useAppStore(state => state.systemStatus);
export const useMarketData = () => useAppStore(state => state.marketData);
export const useEquityCurve = () => useAppStore(state => state.equityCurve);
export const useLatencyHistory = () => useAppStore(state => state.latencyHistory);

// Actions selectors - Individual selectors to prevent infinite re-renders
export const useSetConnected = () => useAppStore(state => state.setConnected);
export const useUpdateSystemStatus = () => useAppStore(state => state.updateSystemStatus);
export const useSetPositions = () => useAppStore(state => state.setPositions);
export const useUpdatePosition = () => useAppStore(state => state.updatePosition);
export const useRemovePosition = () => useAppStore(state => state.removePosition);
export const useSetOrders = () => useAppStore(state => state.setOrders);
export const useUpdateOrder = () => useAppStore(state => state.updateOrder);
export const useAddOrder = () => useAppStore(state => state.addOrder);
export const useSetStrategies = () => useAppStore(state => state.setStrategies);
export const useUpdateStrategy = () => useAppStore(state => state.updateStrategy);
export const useSetSelectedStrategy = () => useAppStore(state => state.setSelectedStrategy);
export const useUpdateMarketData = () => useAppStore(state => state.updateMarketData);
export const useUpdateRiskMetrics = () => useAppStore(state => state.updateRiskMetrics);
export const useAddAlert = () => useAppStore(state => state.addAlert);
export const useAcknowledgeAlert = () => useAppStore(state => state.acknowledgeAlert);
export const useClearAlerts = () => useAppStore(state => state.clearAlerts);
export const useToggleDarkMode = () => useAppStore(state => state.toggleDarkMode);
export const useToggleSidebar = () => useAppStore(state => state.toggleSidebar);
export const useUpdateEquityCurve = () => useAppStore(state => state.updateEquityCurve);
export const useUpdateLatencyHistory = () => useAppStore(state => state.updateLatencyHistory);
export const useKillAllPositions = () => useAppStore(state => state.killAllPositions);
export const useGenerateMockEquityData = () => useAppStore(state => state.generateMockEquityData);
export const useGenerateMockPositions = () => useAppStore(state => state.generateMockPositions);
export const useGenerateMockStrategies = () => useAppStore(state => state.generateMockStrategies);

// Backward compatibility - deprecated, use individual selectors instead
export const useAppActions = () => ({
  setConnected: useSetConnected(),
  updateSystemStatus: useUpdateSystemStatus(),
  setPositions: useSetPositions(),
  updatePosition: useUpdatePosition(),
  removePosition: useRemovePosition(),
  setOrders: useSetOrders(),
  updateOrder: useUpdateOrder(),
  addOrder: useAddOrder(),
  setStrategies: useSetStrategies(),
  updateStrategy: useUpdateStrategy(),
  setSelectedStrategy: useSetSelectedStrategy(),
  updateMarketData: useUpdateMarketData(),
  updateRiskMetrics: useUpdateRiskMetrics(),
  addAlert: useAddAlert(),
  acknowledgeAlert: useAcknowledgeAlert(),
  clearAlerts: useClearAlerts(),
  toggleDarkMode: useToggleDarkMode(),
  toggleSidebar: useToggleSidebar(),
  updateEquityCurve: useUpdateEquityCurve(),
  updateLatencyHistory: useUpdateLatencyHistory(),
  killAllPositions: useKillAllPositions(),
  generateMockEquityData: useGenerateMockEquityData(),
  generateMockPositions: useGenerateMockPositions(),
  generateMockStrategies: useGenerateMockStrategies(),
}); 