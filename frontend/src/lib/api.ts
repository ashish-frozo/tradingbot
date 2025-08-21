const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// API response types
export interface ApiResponse<T> {
  data: T;
  status: 'success' | 'error';
  message?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// API client class
export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Health check
  async health(): Promise<ApiResponse<{ status: string; timestamp: string }>> {
    return this.request('/health');
  }

  // Position endpoints
  async getPositions(): Promise<ApiResponse<any[]>> {
    return this.request('/api/positions');
  }

  async getPosition(symbol: string): Promise<ApiResponse<any>> {
    return this.request(`/api/positions/${symbol}`);
  }

  // Order endpoints
  async getOrders(): Promise<ApiResponse<any[]>> {
    return this.request('/api/orders');
  }

  async placeOrder(order: any): Promise<ApiResponse<any>> {
    return this.request('/api/orders', {
      method: 'POST',
      body: JSON.stringify(order),
    });
  }

  async cancelOrder(orderId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/orders/${orderId}`, {
      method: 'DELETE',
    });
  }

  // Strategy endpoints
  async getStrategies(): Promise<ApiResponse<any[]>> {
    return this.request('/api/strategies');
  }

  async getStrategy(strategyId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/strategies/${strategyId}`);
  }

  async updateStrategy(strategyId: string, data: any): Promise<ApiResponse<any>> {
    return this.request(`/api/strategies/${strategyId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async startStrategy(strategyId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/strategies/${strategyId}/start`, {
      method: 'POST',
    });
  }

  async stopStrategy(strategyId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/strategies/${strategyId}/stop`, {
      method: 'POST',
    });
  }

  // Risk endpoints
  async getRiskMetrics(): Promise<ApiResponse<any>> {
    return this.request('/api/risk/metrics');
  }

  async updateRiskLimits(limits: any): Promise<ApiResponse<any>> {
    return this.request('/api/risk/limits', {
      method: 'PUT',
      body: JSON.stringify(limits),
    });
  }

  // Emergency actions
  async killAllPositions(): Promise<ApiResponse<any>> {
    return this.request('/api/emergency/kill-all', {
      method: 'POST',
    });
  }

  // Dashboard data
  async getDashboardData(): Promise<ApiResponse<any>> {
    return this.request('/api/dashboard');
  }

  // Historical data
  async getHistoricalData(params: {
    symbol?: string;
    start_date?: string;
    end_date?: string;
    interval?: string;
  }): Promise<ApiResponse<any[]>> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) searchParams.append(key, value);
    });
    
    return this.request(`/api/historical?${searchParams}`);
  }

  // Market data
  async getMarketData(symbols: string[]): Promise<ApiResponse<any[]>> {
    return this.request('/api/market-data', {
      method: 'POST',
      body: JSON.stringify({ symbols }),
    });
  }

  // System status
  async getSystemStatus(): Promise<ApiResponse<any>> {
    return this.request('/api/system/status');
  }

  // Alerts
  async getAlerts(): Promise<ApiResponse<any[]>> {
    return this.request('/api/alerts');
  }

  async acknowledgeAlert(alertId: string): Promise<ApiResponse<any>> {
    return this.request(`/api/alerts/${alertId}/acknowledge`, {
      method: 'POST',
    });
  }

  async clearAlerts(): Promise<ApiResponse<any>> {
    return this.request('/api/alerts', {
      method: 'DELETE',
    });
  }
}

// Create singleton instance
export const apiClient = new ApiClient();

// Export default instance
export default apiClient; 