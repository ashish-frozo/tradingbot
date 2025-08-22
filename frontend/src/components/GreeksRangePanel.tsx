import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';

interface GreeksRangeData {
  center: number;
  support: number;
  resistance: number;
  support2?: number;
  resistance2?: number;
  zero_gamma: number;
  gamma_wall_low: number;
  gamma_wall_high: number;
  gex_regime: string;
  expected_move: number;
  charm_modifier: number;
  vanna_shift: number;
  timestamp: string;
  trading_strategy: {
    type: string;
    description: string;
    strategy: string;
    key_level?: number;
    bias: string;
  };
  error?: string;
}

const GreeksRangePanel: React.FC = () => {
  const [rangeData, setRangeData] = useState<GreeksRangeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRangeData = async () => {
    try {
      setLoading(true);
      const data = await apiService.getGreeksRange();
      setRangeData(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch Greeks range data');
      console.error('Error fetching Greeks range:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRangeData();
    // Refresh every 2 minutes
    const interval = setInterval(fetchRangeData, 120000);
    return () => clearInterval(interval);
  }, []);

  const getRegimeColor = (regime: string) => {
    switch (regime) {
      case 'long_gamma': return 'text-blue-600 bg-blue-100';
      case 'short_gamma': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getBiasColor = (bias: string) => {
    switch (bias) {
      case 'directional': return 'text-orange-600';
      case 'neutral': return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Greeks Range Model</h3>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error || !rangeData) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Greeks Range Model</h3>
        <div className="text-red-600">
          {error || 'No data available'}
        </div>
        <button 
          onClick={fetchRangeData}
          className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Greeks Range Model</h3>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${getRegimeColor(rangeData.gex_regime)}`}>
          {rangeData.gex_regime.replace('_', ' ').toUpperCase()}
        </div>
      </div>

      {/* Primary Levels */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center">
          <div className="text-sm text-gray-500 mb-1">Support</div>
          <div className="text-xl font-bold text-red-600">
            {rangeData.support.toLocaleString()}
          </div>
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-500 mb-1">Center</div>
          <div className="text-xl font-bold text-blue-600">
            {rangeData.center.toLocaleString()}
          </div>
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-500 mb-1">Resistance</div>
          <div className="text-xl font-bold text-green-600">
            {rangeData.resistance.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Secondary Levels (if available) */}
      {(rangeData.support2 || rangeData.resistance2) && (
        <div className="grid grid-cols-2 gap-4 mb-6 border-t pt-4">
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Support 2</div>
            <div className="text-lg font-semibold text-red-500">
              {rangeData.support2?.toLocaleString() || 'N/A'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Resistance 2</div>
            <div className="text-lg font-semibold text-green-500">
              {rangeData.resistance2?.toLocaleString() || 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* Trading Strategy */}
      <div className="bg-gray-50 rounded-lg p-4 mb-4">
        <div className="flex justify-between items-start mb-2">
          <h4 className="font-semibold text-gray-800">{rangeData.trading_strategy.type}</h4>
          <span className={`text-sm font-medium ${getBiasColor(rangeData.trading_strategy.bias)}`}>
            {rangeData.trading_strategy.bias.toUpperCase()}
          </span>
        </div>
        <p className="text-sm text-gray-600 mb-2">{rangeData.trading_strategy.description}</p>
        <p className="text-sm text-gray-700 font-medium">{rangeData.trading_strategy.strategy}</p>
        {rangeData.trading_strategy.key_level && (
          <div className="mt-2 text-sm">
            <span className="text-gray-500">Key Level: </span>
            <span className="font-semibold">{rangeData.trading_strategy.key_level.toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Technical Details */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-gray-500">Zero Gamma</div>
          <div className="font-semibold">{rangeData.zero_gamma.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-gray-500">Expected Move</div>
          <div className="font-semibold">±{rangeData.expected_move.toFixed(0)}</div>
        </div>
        <div>
          <div className="text-gray-500">Gamma Walls</div>
          <div className="font-semibold">
            {rangeData.gamma_wall_low.toLocaleString()} - {rangeData.gamma_wall_high.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-gray-500">Charm Modifier</div>
          <div className="font-semibold">{rangeData.charm_modifier.toFixed(2)}x</div>
        </div>
        <div>
          <div className="text-gray-500">Vanna Shift</div>
          <div className="font-semibold">
            {rangeData.vanna_shift > 0 ? '+' : ''}{rangeData.vanna_shift.toFixed(1)}
          </div>
        </div>
        <div>
          <div className="text-gray-500">Updated</div>
          <div className="font-semibold">
            {new Date(rangeData.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* Visual Range Indicator */}
      <div className="mt-6">
        <div className="text-sm text-gray-500 mb-2">Range Visualization</div>
        <div className="relative h-8 bg-gray-200 rounded-full overflow-hidden">
          {/* Support to Resistance range */}
          <div 
            className="absolute h-full bg-blue-200"
            style={{
              left: `${Math.max(0, (rangeData.support - rangeData.gamma_wall_low) / (rangeData.gamma_wall_high - rangeData.gamma_wall_low) * 100)}%`,
              width: `${Math.min(100, (rangeData.resistance - rangeData.support) / (rangeData.gamma_wall_high - rangeData.gamma_wall_low) * 100)}%`
            }}
          ></div>
          
          {/* Center marker */}
          <div 
            className="absolute w-1 h-full bg-blue-600"
            style={{
              left: `${(rangeData.center - rangeData.gamma_wall_low) / (rangeData.gamma_wall_high - rangeData.gamma_wall_low) * 100}%`
            }}
          ></div>
          
          {/* Support marker */}
          <div 
            className="absolute w-1 h-full bg-red-600"
            style={{
              left: `${(rangeData.support - rangeData.gamma_wall_low) / (rangeData.gamma_wall_high - rangeData.gamma_wall_low) * 100}%`
            }}
          ></div>
          
          {/* Resistance marker */}
          <div 
            className="absolute w-1 h-full bg-green-600"
            style={{
              left: `${(rangeData.resistance - rangeData.gamma_wall_low) / (rangeData.gamma_wall_high - rangeData.gamma_wall_low) * 100}%`
            }}
          ></div>
        </div>
        
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>{rangeData.gamma_wall_low.toLocaleString()}</span>
          <span>{rangeData.gamma_wall_high.toLocaleString()}</span>
        </div>
      </div>

      {rangeData.error && (
        <div className="mt-4 p-3 bg-yellow-100 border border-yellow-400 rounded text-sm text-yellow-800">
          <strong>Note:</strong> Using fallback data due to: {rangeData.error}
        </div>
      )}
    </div>
  );
};

export default GreeksRangePanel;
