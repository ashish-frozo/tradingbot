import React from 'react';
import { useRiskMetrics } from '../hooks/useApiData';

export const SimpleRiskPanel: React.FC = () => {
  const { data: riskMetrics, loading, error } = useRiskMetrics();

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Risk Management</h2>
        <div className="flex items-center justify-center h-32">
          <div className="text-gray-500">Loading risk metrics...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Risk Management</h2>
        <div className="flex items-center justify-center h-32">
          <div className="text-red-500">Error loading risk metrics: {error}</div>
        </div>
      </div>
    );
  }

  if (!riskMetrics) {
    return null;
  }

  const marginUtilization = riskMetrics.margin_used / (riskMetrics.margin_used + riskMetrics.margin_available) * 100;
  const lossLimitUtilization = Math.abs(riskMetrics.day_pnl) / riskMetrics.max_loss_limit * 100;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Risk Management</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* P&L Overview */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-gray-800">P&L Overview</h3>
          
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Total P&L:</span>
              <span className={`font-semibold ${riskMetrics.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {riskMetrics.total_pnl >= 0 ? '+' : ''}₹{riskMetrics.total_pnl.toFixed(2)}
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Day P&L:</span>
              <span className={`font-semibold ${riskMetrics.day_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {riskMetrics.day_pnl >= 0 ? '+' : ''}₹{riskMetrics.day_pnl.toFixed(2)}
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Max Loss Limit:</span>
              <span className="font-semibold text-red-600">
                -₹{riskMetrics.max_loss_limit.toFixed(2)}
              </span>
            </div>
            
            {/* Loss Limit Progress Bar */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Loss Limit Usage:</span>
                <span className={`font-medium ${lossLimitUtilization > 80 ? 'text-red-600' : lossLimitUtilization > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                  {lossLimitUtilization.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full transition-all duration-300 ${
                    lossLimitUtilization > 80 ? 'bg-red-500' : 
                    lossLimitUtilization > 60 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(lossLimitUtilization, 100)}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Margin & Positions */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-gray-800">Margin & Positions</h3>
          
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Margin Used:</span>
              <span className="font-semibold text-blue-600">
                ₹{riskMetrics.margin_used.toLocaleString('en-IN')}
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Margin Available:</span>
              <span className="font-semibold text-green-600">
                ₹{riskMetrics.margin_available.toLocaleString('en-IN')}
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Open Positions:</span>
              <span className="font-semibold text-gray-800">
                {riskMetrics.position_count}
              </span>
            </div>
            
            {/* Margin Usage Progress Bar */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Margin Usage:</span>
                <span className={`font-medium ${marginUtilization > 80 ? 'text-red-600' : marginUtilization > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                  {marginUtilization.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full transition-all duration-300 ${
                    marginUtilization > 80 ? 'bg-red-500' : 
                    marginUtilization > 60 ? 'bg-yellow-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${Math.min(marginUtilization, 100)}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Alerts */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <h3 className="text-lg font-medium text-gray-800 mb-3">Risk Alerts</h3>
        
        <div className="space-y-2">
          {lossLimitUtilization > 90 && (
            <div className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <span className="text-red-500 text-lg">🚨</span>
              <span className="text-red-700 font-medium">
                Critical: Approaching daily loss limit ({lossLimitUtilization.toFixed(1)}%)
              </span>
            </div>
          )}
          
          {marginUtilization > 85 && (
            <div className="flex items-center space-x-2 p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <span className="text-orange-500 text-lg">⚠️</span>
              <span className="text-orange-700 font-medium">
                High margin usage: {marginUtilization.toFixed(1)}% - Consider reducing positions
              </span>
            </div>
          )}
          
          {riskMetrics.position_count > 10 && (
            <div className="flex items-center space-x-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <span className="text-yellow-500 text-lg">📊</span>
              <span className="text-yellow-700 font-medium">
                High position count: {riskMetrics.position_count} positions open
              </span>
            </div>
          )}
          
          {lossLimitUtilization < 30 && marginUtilization < 50 && riskMetrics.position_count < 5 && (
            <div className="flex items-center space-x-2 p-3 bg-green-50 border border-green-200 rounded-lg">
              <span className="text-green-500 text-lg">✅</span>
              <span className="text-green-700 font-medium">
                All risk metrics within safe parameters
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
