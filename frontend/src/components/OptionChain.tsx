import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { formatCurrency } from '../lib/utils';

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
  success: boolean;
  data: OptionChainRow[];
  timestamp: string;
  underlying: string;
  spot_price: number;
  expiry: string;
}

export const OptionChain: React.FC = () => {
  const [optionData, setOptionData] = useState<OptionChainData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedStrike, setSelectedStrike] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'prices' | 'greeks' | 'volume'>('prices');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOptionChain();
    const interval = setInterval(fetchOptionChain, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchOptionChain = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/option-chain');
      const rawData = await response.json();
      
      // Handle different response statuses
      if (rawData.status === 'success' && rawData.data) {
        // Transform successful API response
        const transformedData = {
          success: true,
          data: rawData.data.map((item: any) => ({
            strike: item['Strike Price'],
            call: {
              ltp: item['CE LTP'],
              bid: item['CE Bid'],
              ask: item['CE Ask'],
              volume: item['CE Volume'],
              oi: item['CE OI'],
              iv: item['CE IV'],
              delta: 0.5, // Mock values since not in API
              gamma: 0.01,
              theta: -0.05,
              vega: 0.1
            },
            put: {
              ltp: item['PE LTP'],
              bid: item['PE Bid'],
              ask: item['PE Ask'],
              volume: item['PE Volume'],
              oi: item['PE OI'],
              iv: item['PE IV'],
              delta: -0.5, // Mock values since not in API
              gamma: 0.01,
              theta: -0.05,
              vega: 0.1
            }
          })),
          timestamp: rawData.timestamp,
          underlying: 'NIFTY',
          spot_price: 25107.35,
          expiry: '2025-08-28'
        };
        setOptionData(transformedData);
        setError(null);
      } else if (rawData.status === 'blocked') {
        // Handle kill switch scenarios
        const message = rawData.message || 'Data fetching is currently disabled';
        if (rawData.reason === 'outside_market_hours') {
          setError(`🕐 ${message}`);
        } else if (rawData.reason === 'manual_kill_switch') {
          setError(`🔴 ${message}`);
        } else if (rawData.reason === 'emergency_stop') {
          setError(`🚨 ${message}`);
        } else {
          setError(`🚫 ${message}`);
        }
        setOptionData(null);
      } else {
        // Handle other error statuses
        const message = rawData.message || rawData.note || 'Failed to load option chain data';
        setError(message);
        setOptionData(null);
      }
      setLoading(false);
    } catch (error) {
      console.error('Error fetching option chain:', error);
      setError('Network error: Unable to connect to the server');
      setOptionData(null);
      setLoading(false);
    }
  };

  const getATMStrike = () => {
    if (!optionData) return null;
    const spotPrice = optionData.spot_price;
    return optionData.data.reduce((closest, row) => {
      return Math.abs(row.strike - spotPrice) < Math.abs(closest.strike - spotPrice) ? row : closest;
    }).strike;
  };

  const getStrikeColor = (strike: number) => {
    if (!optionData) return '';
    const spotPrice = optionData.spot_price;
    const atmStrike = getATMStrike();
    
    if (strike === atmStrike) return 'bg-yellow-100 dark:bg-yellow-900';
    if (strike < spotPrice) return 'bg-green-50 dark:bg-green-900/20';
    return 'bg-red-50 dark:bg-red-900/20';
  };

  const renderOptionData = (option: OptionData, type: 'call' | 'put') => {
    switch (viewMode) {
      case 'greeks':
        return (
          <div className="space-y-1 text-xs">
            <div>Δ: {option.delta.toFixed(3)}</div>
            <div>Γ: {option.gamma.toFixed(4)}</div>
            <div>Θ: {option.theta.toFixed(2)}</div>
            <div>ν: {option.vega.toFixed(2)}</div>
          </div>
        );
      case 'volume':
        return (
          <div className="space-y-1 text-xs">
            <div>Vol: {option.volume.toLocaleString()}</div>
            <div>OI: {option.oi.toLocaleString()}</div>
            <div>IV: {option.iv.toFixed(1)}%</div>
            <div>B/A: {option.bid}/{option.ask}</div>
          </div>
        );
      default:
        return (
          <div className="space-y-1">
            <div className={`font-bold text-lg ${type === 'call' ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(option.ltp)}
            </div>
            <div className="text-xs text-gray-500">
              {option.bid} / {option.ask}
            </div>
          </div>
        );
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Option Chain</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Option Chain</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="text-amber-600 dark:text-amber-400 mb-2 text-lg">
              {error}
            </div>
            <div className="text-sm text-gray-500">
              {error.includes('market hours') && (
                <div>
                  <p>Market is currently closed (9:15 AM - 3:30 PM IST)</p>
                  <p className="mt-1 text-xs">Data fetching will resume automatically when market opens</p>
                </div>
              )}
              {error.includes('Manual kill switch') && (
                <div>
                  <p>Data fetching has been manually disabled</p>
                  <p className="mt-1 text-xs">Contact administrator to re-enable</p>
                </div>
              )}
              {error.includes('Emergency') && (
                <div>
                  <p>Emergency stop is active</p>
                  <p className="mt-1 text-xs">All data fetching has been halted</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!optionData || !optionData.success) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Option Chain</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-500">
            No option chain data available
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              Option Chain - {optionData.underlying}
              <Badge variant="outline">
                Spot: {formatCurrency(optionData.spot_price)}
              </Badge>
            </CardTitle>
            <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Expiry: {optionData.expiry} | Last Updated: {new Date(optionData.timestamp).toLocaleTimeString()}
            </div>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant={viewMode === 'prices' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('prices')}
            >
              Prices
            </Button>
            <Button
              variant={viewMode === 'greeks' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('greeks')}
            >
              Greeks
            </Button>
            <Button
              variant={viewMode === 'volume' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('volume')}
            >
              Volume
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left p-2 font-medium text-green-600">CALL</th>
                <th className="text-center p-2 font-medium">STRIKE</th>
                <th className="text-right p-2 font-medium text-red-600">PUT</th>
              </tr>
            </thead>
            <tbody>
              {optionData.data.map((row) => (
                <tr
                  key={row.strike}
                  className={`border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer ${getStrikeColor(row.strike)} ${
                    selectedStrike === row.strike ? 'ring-2 ring-blue-500' : ''
                  }`}
                  onClick={() => setSelectedStrike(selectedStrike === row.strike ? null : row.strike)}
                >
                  <td className="p-2 text-left">
                    {renderOptionData(row.call, 'call')}
                  </td>
                  <td className="p-2 text-center">
                    <div className="font-bold text-lg">
                      {row.strike}
                      {row.strike === getATMStrike() && (
                        <Badge variant="secondary" className="ml-1 text-xs">ATM</Badge>
                      )}
                    </div>
                  </td>
                  <td className="p-2 text-right">
                    {renderOptionData(row.put, 'put')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {selectedStrike && (
          <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <h4 className="font-semibold mb-2">Strike {selectedStrike} Details</h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              {(() => {
                const row = optionData.data.find(r => r.strike === selectedStrike);
                if (!row) return null;
                
                return (
                  <>
                    <div>
                      <div className="font-medium text-green-600 mb-1">CALL</div>
                      <div>LTP: {formatCurrency(row.call.ltp)}</div>
                      <div>Volume: {row.call.volume.toLocaleString()}</div>
                      <div>OI: {row.call.oi.toLocaleString()}</div>
                      <div>IV: {row.call.iv.toFixed(1)}%</div>
                      <div>Delta: {row.call.delta.toFixed(3)}</div>
                    </div>
                    <div>
                      <div className="font-medium text-red-600 mb-1">PUT</div>
                      <div>LTP: {formatCurrency(row.put.ltp)}</div>
                      <div>Volume: {row.put.volume.toLocaleString()}</div>
                      <div>OI: {row.put.oi.toLocaleString()}</div>
                      <div>IV: {row.put.iv.toFixed(1)}%</div>
                      <div>Delta: {row.put.delta.toFixed(3)}</div>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
