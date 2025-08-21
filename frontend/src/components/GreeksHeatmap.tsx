import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

interface OptionData {
  ltp: number;
  bid: number;
  ask: number;
  volume: number;
  oi: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
}

interface OptionChainRow {
  strike: number;
  call: OptionData;
  put: OptionData;
}

interface OptionChainData {
  spot_price: number;
  data: OptionChainRow[];
}

export const GreeksHeatmap: React.FC = () => {
  const [optionData, setOptionData] = useState<OptionChainData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedGreek, setSelectedGreek] = useState<'delta' | 'gamma' | 'theta' | 'vega'>('delta');

  useEffect(() => {
    fetchOptionChain();
    const interval = setInterval(fetchOptionChain, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchOptionChain = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/option-chain');
      if (response.ok) {
        const data = await response.json();
        setOptionData(data);
      }
    } catch (error) {
      console.error('Error fetching option chain:', error);
    } finally {
      setLoading(false);
    }
  };

  const getGreekValue = (option: OptionData, greek: string) => {
    switch (greek) {
      case 'delta': return option.delta;
      case 'gamma': return option.gamma;
      case 'theta': return option.theta || 0;
      case 'vega': return option.vega || 0;
      default: return 0;
    }
  };

  const getHeatmapColor = (value: number, greek: string) => {
    let intensity = 0;
    
    switch (greek) {
      case 'delta':
        intensity = Math.abs(value);
        break;
      case 'gamma':
        intensity = Math.min(value * 100, 1);
        break;
      case 'theta':
        intensity = Math.min(Math.abs(value) / 50, 1);
        break;
      case 'vega':
        intensity = Math.min(Math.abs(value) / 100, 1);
        break;
    }

    const opacity = Math.max(0.1, Math.min(intensity, 0.9));
    
    if (value > 0) {
      return `rgba(34, 197, 94, ${opacity})`; // Green for positive
    } else if (value < 0) {
      return `rgba(239, 68, 68, ${opacity})`; // Red for negative
    } else {
      return 'rgba(156, 163, 175, 0.1)'; // Gray for zero
    }
  };

  const formatGreekValue = (value: number, greek: string) => {
    switch (greek) {
      case 'delta':
        return value.toFixed(3);
      case 'gamma':
        return value.toFixed(4);
      case 'theta':
        return value.toFixed(2);
      case 'vega':
        return value.toFixed(2);
      default:
        return value.toFixed(2);
    }
  };

  const getGreekDescription = (greek: string) => {
    switch (greek) {
      case 'delta':
        return 'Price sensitivity to underlying movement. Calls: 0 to 1, Puts: -1 to 0';
      case 'gamma':
        return 'Rate of change of delta. Higher gamma = more delta acceleration';
      case 'theta':
        return 'Time decay. Negative values indicate daily premium loss';
      case 'vega':
        return 'Volatility sensitivity. Higher vega = more IV impact';
      default:
        return '';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center">Loading Greeks data...</div>
        </CardContent>
      </Card>
    );
  }

  if (!optionData) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center text-red-500">Failed to load option chain data</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Greek Selection */}
      <div className="flex space-x-2 flex-wrap">
        <Button
          variant={selectedGreek === 'delta' ? 'default' : 'outline'}
          onClick={() => setSelectedGreek('delta')}
        >
          Δ Delta
        </Button>
        <Button
          variant={selectedGreek === 'gamma' ? 'default' : 'outline'}
          onClick={() => setSelectedGreek('gamma')}
        >
          Γ Gamma
        </Button>
        <Button
          variant={selectedGreek === 'theta' ? 'default' : 'outline'}
          onClick={() => setSelectedGreek('theta')}
        >
          Θ Theta
        </Button>
        <Button
          variant={selectedGreek === 'vega' ? 'default' : 'outline'}
          onClick={() => setSelectedGreek('vega')}
        >
          ν Vega
        </Button>
      </div>

      {/* Greeks Heatmap */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>🔥 {selectedGreek.toUpperCase()} Heatmap</span>
            <Badge variant="outline">Live</Badge>
          </CardTitle>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {getGreekDescription(selectedGreek)}
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <div className="min-w-full">
              {/* Header */}
              <div className="grid grid-cols-5 gap-2 mb-2 text-sm font-semibold">
                <div className="text-center">Strike</div>
                <div className="text-center text-green-600">Call {selectedGreek.toUpperCase()}</div>
                <div className="text-center">Spot</div>
                <div className="text-center text-red-600">Put {selectedGreek.toUpperCase()}</div>
                <div className="text-center">Moneyness</div>
              </div>

              {/* Heatmap Rows */}
              <div className="space-y-1">
                {optionData.data.map((row, index) => {
                  const callValue = getGreekValue(row.call, selectedGreek);
                  const putValue = getGreekValue(row.put, selectedGreek);
                  const isATM = Math.abs(row.strike - optionData.spot_price) < 50;
                  const moneyness = ((row.strike - optionData.spot_price) / optionData.spot_price) * 100;

                  return (
                    <div key={index} className={`grid grid-cols-5 gap-2 py-2 px-1 rounded text-sm ${isATM ? 'ring-2 ring-blue-500' : ''}`}>
                      {/* Strike */}
                      <div className="text-center font-medium">
                        {row.strike}
                      </div>

                      {/* Call Greek */}
                      <div 
                        className="text-center p-2 rounded font-mono"
                        style={{ backgroundColor: getHeatmapColor(callValue, selectedGreek) }}
                      >
                        {formatGreekValue(callValue, selectedGreek)}
                      </div>

                      {/* Spot Indicator */}
                      <div className="text-center text-xs text-gray-500 flex items-center justify-center">
                        {isATM ? '📍 ATM' : ''}
                      </div>

                      {/* Put Greek */}
                      <div 
                        className="text-center p-2 rounded font-mono"
                        style={{ backgroundColor: getHeatmapColor(putValue, selectedGreek) }}
                      >
                        {formatGreekValue(putValue, selectedGreek)}
                      </div>

                      {/* Moneyness */}
                      <div className="text-center text-xs">
                        <span className={moneyness > 0 ? 'text-red-500' : 'text-green-500'}>
                          {moneyness > 0 ? '+' : ''}{moneyness.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Legend */}
          <div className="mt-6 flex items-center justify-center space-x-6 text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgba(34, 197, 94, 0.7)' }}></div>
              <span>Positive Values</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.7)' }}></div>
              <span>Negative Values</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 rounded ring-2 ring-blue-500"></div>
              <span>ATM Strikes</span>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded">
              <div className="font-semibold text-green-600">Max Call {selectedGreek.toUpperCase()}</div>
              <div className="font-mono">
                {formatGreekValue(
                  Math.max(...optionData.data.map(row => getGreekValue(row.call, selectedGreek))),
                  selectedGreek
                )}
              </div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded">
              <div className="font-semibold text-red-600">Min Put {selectedGreek.toUpperCase()}</div>
              <div className="font-mono">
                {formatGreekValue(
                  Math.min(...optionData.data.map(row => getGreekValue(row.put, selectedGreek))),
                  selectedGreek
                )}
              </div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded">
              <div className="font-semibold text-blue-600">ATM Call {selectedGreek.toUpperCase()}</div>
              <div className="font-mono">
                {(() => {
                  const atmRow = optionData.data.find(row => Math.abs(row.strike - optionData.spot_price) < 50);
                  return atmRow ? formatGreekValue(getGreekValue(atmRow.call, selectedGreek), selectedGreek) : 'N/A';
                })()}
              </div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded">
              <div className="font-semibold text-purple-600">ATM Put {selectedGreek.toUpperCase()}</div>
              <div className="font-mono">
                {(() => {
                  const atmRow = optionData.data.find(row => Math.abs(row.strike - optionData.spot_price) < 50);
                  return atmRow ? formatGreekValue(getGreekValue(atmRow.put, selectedGreek), selectedGreek) : 'N/A';
                })()}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default GreeksHeatmap;
