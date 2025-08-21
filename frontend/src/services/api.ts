/**
 * API service for communicating with the backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export interface EquityData {
  dates: string[];
  equity: number[];
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  ltp: number;
  pnl: number;
  pnl_percent: number;
}

export interface PositionsResponse {
  positions: Position[];
  total_pnl: number;
  total_pnl_percent: number;
}

export interface MarketData {
  nifty: {
    ltp: number;
    change: number;
    change_percent: number;
  };
  banknifty: {
    ltp: number;
    change: number;
    change_percent: number;
  };
  timestamp: string;
}

export interface RiskMetrics {
  daily_pnl: number;
  max_daily_loss_limit: number;
  current_exposure: number;
  max_exposure_limit: number;
  var_95: number;
  portfolio_delta: number;
  portfolio_gamma: number;
  portfolio_theta: number;
}

class ApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      throw error;
    }
  }

  async getHealth(): Promise<{ status: string; timestamp: string }> {
    return this.request('/health');
  }

  async getEquityData(): Promise<EquityData> {
    return this.request('/api/equity-data');
  }

  async getPositions(): Promise<PositionsResponse> {
    return this.request('/api/positions');
  }

  async getMarketData(): Promise<MarketData> {
    return this.request('/api/market-data');
  }

  async getRiskMetrics(): Promise<RiskMetrics> {
    return this.request('/api/risk-metrics');
  }
}

export const apiService = new ApiService();
