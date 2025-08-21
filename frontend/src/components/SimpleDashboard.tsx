import React from 'react';
import { EquityCurve } from './EquityCurve';
import { PositionsTable } from './PositionsTable';
import { SimpleRiskPanel } from './SimpleRiskPanel';
import { useEquityData, usePositions, useRiskMetrics, useMarketData } from '../hooks/useApiData';
import { useAppStore } from '../store/appStore';

export const SimpleDashboard: React.FC = () => {
  // Load all data from APIs
  const { data: equityData, loading: equityLoading, error: equityError } = useEquityData();
  const { positions } = useAppStore();
  const { data: riskMetrics, loading: riskLoading, error: riskError } = useRiskMetrics();
  const { data: marketData, loading: marketLoading, error: marketError } = useMarketData();

  const isLoading = equityLoading || riskLoading || marketLoading;
  const hasError = equityError || riskError || marketError;

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          Nifty Trade Setup Dashboard
        </h1>
        
        {/* Connection Status */}
        <div className="mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${isLoading ? 'bg-yellow-500' : hasError ? 'bg-red-500' : 'bg-green-500'}`}></div>
                <span className="text-sm font-medium">
                  {isLoading ? 'Loading...' : hasError ? 'Connection Issues' : 'All Systems Connected'}
                </span>
              </div>
              <div className="text-sm text-gray-600">
                Real Dhan API • Live Data
              </div>
            </div>
          </div>
        </div>

        {/* Main Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Equity Curve */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Equity Curve</h2>
              {equityLoading ? (
                <div className="flex items-center justify-center h-64">
                  <div className="text-gray-500">Loading equity data...</div>
                </div>
              ) : equityError ? (
                <div className="flex items-center justify-center h-64">
                  <div className="text-red-500">Error: {equityError}</div>
                </div>
              ) : (
                <EquityCurve height={300} />
              )}
            </div>
          </div>
          
          {/* Performance Stats */}
          <div className="space-y-4">
            {equityData && (
              <>
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="text-lg font-medium mb-2">Performance</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Total Return:</span>
                      <span className={`font-medium ${equityData.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {equityData.total_return.toFixed(2)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Max Drawdown:</span>
                      <span className="font-medium text-red-600">
                        {equityData.max_drawdown}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Sharpe Ratio:</span>
                      <span className="font-medium text-blue-600">
                        {equityData.sharpe_ratio}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="text-lg font-medium mb-2">Portfolio Value</h3>
                  <div className="text-2xl font-bold text-gray-900">
                    ₹{equityData.equity[equityData.equity.length - 1]?.toLocaleString('en-IN')}
                  </div>
                  <div className="text-sm text-gray-600">
                    Starting: ₹{equityData.equity[0]?.toLocaleString('en-IN')}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Positions and Risk Management */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <PositionsTable />
          <SimpleRiskPanel />
        </div>

        {/* Market Data and System Status */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Market Data */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Market Overview</h2>
            {marketLoading ? (
              <div className="text-gray-500">Loading market data...</div>
            ) : marketError ? (
              <div className="text-red-500">Error: {marketError}</div>
            ) : marketData && marketData.length > 0 ? (
              <div className="space-y-3">
                {marketData.map((item: any, index: number) => (
                  <div key={index} className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="font-medium">{item.symbol}</span>
                    <div className="text-right">
                      <div className="font-semibold">₹{item.ltp.toLocaleString('en-IN')}</div>
                      <div className={`text-sm ${item.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {item.change >= 0 ? '+' : ''}₹{item.change} ({item.change_percent.toFixed(2)}%)
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-500">No market data available</div>
            )}
          </div>

          {/* System Status */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">System Status</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Dhan API:</span>
                <span className={`font-medium ${equityError ? 'text-red-600' : 'text-green-600'}`}>
                  {equityError ? 'Disconnected' : 'Connected'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Positions:</span>
                <span className="font-medium text-blue-600">
                  {positions?.length || 0} Open
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Data Points:</span>
                <span className="font-medium text-blue-600">
                  {equityData?.equity.length || 0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Last Update:</span>
                <span className="font-medium text-gray-600">
                  {new Date().toLocaleTimeString()}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Trading Status:</span>
                <span className="font-medium text-green-600">
                  Active
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
