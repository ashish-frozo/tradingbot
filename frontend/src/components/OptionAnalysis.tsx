import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { formatCurrency } from '../lib/utils';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, LineChart, Line } from 'recharts';
import GreeksHeatmap from './GreeksHeatmap';
import VolatilityTermStructure from './VolatilityTermStructure';
import StrategyPnLVisualizer from './StrategyPnLVisualizer';
import RiskManagementDashboard from './RiskManagementDashboard';

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

interface PCRAnalysis {
  totalPCR: number;
  volumePCR: number;
  oiPCR: number;
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  signalStrength: 'STRONG' | 'MODERATE' | 'WEAK';
}

interface MaxPainData {
  maxPainStrike: number;
  maxPainValue: number;
  distanceFromSpot: number;
  distancePercent: number;
}

export const OptionAnalysis: React.FC = () => {
  const [optionData, setOptionData] = useState<OptionChainData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'pcr' | 'maxpain' | 'ivskew' | 'oi' | 'greeks' | 'volterm' | 'strategy' | 'risk'>('pcr');

  useEffect(() => {
    fetchOptionChain();
    const interval = setInterval(fetchOptionChain, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchOptionChain = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/option-chain');
      const rawData = await response.json();
      
      // Transform API response to match component expectations
      if (rawData.status === 'success' && rawData.data) {
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
      } else {
        setOptionData(null);
      }
      setLoading(false);
    } catch (error) {
      console.error('Error fetching option chain:', error);
      setOptionData(null);
      setLoading(false);
    }
  };

  const calculatePCR = (): PCRAnalysis => {
    if (!optionData || !optionData.data) {
      return {
        totalPCR: 0,
        volumePCR: 0,
        oiPCR: 0,
        sentiment: 'NEUTRAL',
        signalStrength: 'WEAK'
      };
    }

    let totalCallOI = 0, totalPutOI = 0;
    let totalCallVolume = 0, totalPutVolume = 0;
    let totalCallValue = 0, totalPutValue = 0;

    optionData.data.forEach(row => {
      totalCallOI += row.call.oi;
      totalPutOI += row.put.oi;
      totalCallVolume += row.call.volume;
      totalPutVolume += row.put.volume;
      totalCallValue += row.call.ltp * row.call.oi;
      totalPutValue += row.put.ltp * row.put.oi;
    });

    const oiPCR = totalCallOI > 0 ? totalPutOI / totalCallOI : 0;
    const volumePCR = totalCallVolume > 0 ? totalPutVolume / totalCallVolume : 0;
    const totalPCR = totalCallValue > 0 ? totalPutValue / totalCallValue : 0;

    let sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL' = 'NEUTRAL';
    let signalStrength: 'STRONG' | 'MODERATE' | 'WEAK' = 'WEAK';

    if (totalPCR < 0.7) {
      sentiment = 'BULLISH';
      signalStrength = totalPCR < 0.5 ? 'STRONG' : 'MODERATE';
    } else if (totalPCR > 1.3) {
      sentiment = 'BEARISH';
      signalStrength = totalPCR > 1.5 ? 'STRONG' : 'MODERATE';
    } else {
      sentiment = 'NEUTRAL';
      signalStrength = 'WEAK';
    }

    return {
      totalPCR: Number(totalPCR.toFixed(3)),
      volumePCR: Number(volumePCR.toFixed(3)),
      oiPCR: Number(oiPCR.toFixed(3)),
      sentiment,
      signalStrength
    };
  };

  const calculateMaxPain = (): MaxPainData => {
    if (!optionData || !optionData.data) {
      return {
        maxPainStrike: 0,
        maxPainValue: 0,
        distanceFromSpot: 0,
        distancePercent: 0
      };
    }

    let maxPainStrike = 0;
    let minPain = Infinity;

    optionData.data.forEach(row => {
      let totalPain = 0;

      // Calculate pain for this strike
      optionData.data.forEach(innerRow => {
        // Call pain: if spot > strike, calls are ITM
        if (row.strike < innerRow.strike) {
          totalPain += (innerRow.strike - row.strike) * innerRow.call.oi;
        }
        
        // Put pain: if spot < strike, puts are ITM
        if (row.strike > innerRow.strike) {
          totalPain += (row.strike - innerRow.strike) * innerRow.put.oi;
        }
      });

      if (totalPain < minPain) {
        minPain = totalPain;
        maxPainStrike = row.strike;
      }
    });

    const distanceFromSpot = maxPainStrike - optionData.spot_price;
    const distancePercent = (distanceFromSpot / optionData.spot_price) * 100;

    return {
      maxPainStrike,
      maxPainValue: minPain,
      distanceFromSpot,
      distancePercent: Number(distancePercent.toFixed(2))
    };
  };

  const getPCRChartData = () => {
    if (!optionData) return [];
    
    return optionData.data.map(row => ({
      strike: row.strike,
      callOI: row.call.oi,
      putOI: row.put.oi,
      pcr: row.call.oi > 0 ? row.put.oi / row.call.oi : 0
    }));
  };

  const getMaxPainChartData = () => {
    if (!optionData) return [];
    
    return optionData.data.map(row => {
      let pain = 0;
      
      optionData.data.forEach(innerRow => {
        if (row.strike < innerRow.strike) {
          pain += (innerRow.strike - row.strike) * innerRow.call.oi;
        }
        if (row.strike > innerRow.strike) {
          pain += (row.strike - innerRow.strike) * innerRow.put.oi;
        }
      });
      
      return {
        strike: row.strike,
        pain: pain / 1000000, // Convert to millions
        isMaxPain: row.strike === calculateMaxPain().maxPainStrike
      };
    });
  };

  const getIVSkewData = () => {
    if (!optionData) return [];
    
    return optionData.data.map(row => ({
      strike: row.strike,
      callIV: row.call.iv,
      putIV: row.put.iv,
      moneyness: ((row.strike - optionData.spot_price) / optionData.spot_price) * 100,
      isATM: Math.abs(row.strike - optionData.spot_price) < 50
    }));
  };

  const getOIAnalysisData = () => {
    if (!optionData) return [];
    
    const totalCallOI = optionData.data.reduce((sum, row) => sum + row.call.oi, 0);
    const totalPutOI = optionData.data.reduce((sum, row) => sum + row.put.oi, 0);
    
    return optionData.data.map(row => ({
      strike: row.strike,
      callOI: row.call.oi,
      putOI: row.put.oi,
      callOIPercent: totalCallOI > 0 ? (row.call.oi / totalCallOI) * 100 : 0,
      putOIPercent: totalPutOI > 0 ? (row.put.oi / totalPutOI) * 100 : 0,
      netOI: row.call.oi - row.put.oi,
      totalOI: row.call.oi + row.put.oi,
      isHighOI: (row.call.oi + row.put.oi) > (totalCallOI + totalPutOI) / optionData.data.length * 1.5
    }));
  };

  const getUnusualActivity = () => {
    if (!optionData) return [];
    
    const avgVolume = optionData.data.reduce((sum, row) => sum + row.call.volume + row.put.volume, 0) / (optionData.data.length * 2);
    
    return optionData.data.filter(row => {
      const callVolumeRatio = row.call.volume / Math.max(row.call.oi, 1);
      const putVolumeRatio = row.put.volume / Math.max(row.put.oi, 1);
      const totalVolume = row.call.volume + row.put.volume;
      
      return totalVolume > avgVolume * 2 || callVolumeRatio > 0.3 || putVolumeRatio > 0.3;
    }).map(row => ({
      strike: row.strike,
      callVolume: row.call.volume,
      putVolume: row.put.volume,
      callOI: row.call.oi,
      putOI: row.put.oi,
      callRatio: row.call.volume / Math.max(row.call.oi, 1),
      putRatio: row.put.volume / Math.max(row.put.oi, 1),
      type: row.call.volume > row.put.volume ? 'CALL_HEAVY' : 'PUT_HEAVY'
    }));
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'BULLISH': return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-200';
      case 'BEARISH': return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-200';
      default: return 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  const getSignalStrengthColor = (strength: string) => {
    switch (strength) {
      case 'STRONG': return 'text-purple-600 bg-purple-100 dark:bg-purple-900 dark:text-purple-200';
      case 'MODERATE': return 'text-blue-600 bg-blue-100 dark:bg-blue-900 dark:text-blue-200';
      default: return 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Option Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!optionData || !optionData.success) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Option Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-500">
            Failed to load option data
          </div>
        </CardContent>
      </Card>
    );
  }

  const pcrData = calculatePCR();
  const maxPainData = calculateMaxPain();

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="flex space-x-2 mb-6 flex-wrap">
        <Button
          variant={activeTab === 'pcr' ? 'default' : 'outline'}
          onClick={() => setActiveTab('pcr')}
        >
          📊 Put-Call Ratio
        </Button>
        <Button
          variant={activeTab === 'maxpain' ? 'default' : 'outline'}
          onClick={() => setActiveTab('maxpain')}
        >
          🎯 Max Pain
        </Button>
        <Button
          variant={activeTab === 'ivskew' ? 'default' : 'outline'}
          onClick={() => setActiveTab('ivskew')}
        >
          📈 IV Skew
        </Button>
        <Button
          variant={activeTab === 'oi' ? 'default' : 'outline'}
          onClick={() => setActiveTab('oi')}
        >
          🔍 OI Analysis
        </Button>
        <Button
          variant={activeTab === 'greeks' ? 'default' : 'outline'}
          onClick={() => setActiveTab('greeks')}
        >
          🔥 Greeks
        </Button>
        <Button
          variant={activeTab === 'volterm' ? 'default' : 'outline'}
          onClick={() => setActiveTab('volterm')}
        >
          📊 Vol Term
        </Button>
        <Button
          variant={activeTab === 'strategy' ? 'default' : 'outline'}
          onClick={() => setActiveTab('strategy')}
        >
          💰 Strategy P&L
        </Button>
        <Button
          variant={activeTab === 'risk' ? 'default' : 'outline'}
          onClick={() => setActiveTab('risk')}
        >
          🛡️ Risk Mgmt
        </Button>
      </div>

      {activeTab === 'volterm' && (
        <div className="space-y-6">
          <VolatilityTermStructure />
        </div>
      )}

      {activeTab === 'strategy' && (
        <div className="space-y-6">
          <StrategyPnLVisualizer />
        </div>
      )}

      {activeTab === 'risk' && (
        <div className="space-y-6">
          <RiskManagementDashboard />
        </div>
      )}

      {activeTab === 'pcr' && (
        <div className="space-y-6">
          {/* PCR Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-blue-600">
                  {pcrData.totalPCR}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Total PCR</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-purple-600">
                  {pcrData.volumePCR}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Volume PCR</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <Badge className={getSentimentColor(pcrData.sentiment)}>
                  {pcrData.sentiment}
                </Badge>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Market Sentiment</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <Badge className={getSignalStrengthColor(pcrData.signalStrength)}>
                  {pcrData.signalStrength}
                </Badge>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Signal Strength</div>
              </CardContent>
            </Card>
          </div>

          {/* PCR Analysis */}
          <Card>
            <CardHeader>
              <CardTitle>Put-Call Ratio Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  <strong>Interpretation:</strong>
                  <ul className="mt-2 space-y-1 list-disc list-inside">
                    <li>PCR &lt; 0.7: Bullish sentiment (more calls than puts)</li>
                    <li>PCR 0.7-1.3: Neutral sentiment (balanced)</li>
                    <li>PCR &gt; 1.3: Bearish sentiment (more puts than calls)</li>
                  </ul>
                </div>
                
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={getPCRChartData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="strike" />
                      <YAxis />
                      <Tooltip 
                        formatter={(value, name) => [
                          name === 'pcr' ? Number(value).toFixed(3) : Number(value).toLocaleString(),
                          name === 'callOI' ? 'Call OI' : name === 'putOI' ? 'Put OI' : 'PCR'
                        ]}
                      />
                      <Bar dataKey="callOI" fill="#10b981" />
                      <Bar dataKey="putOI" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'ivskew' && (
        <div className="space-y-6">
          {/* IV Skew Analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>📈 Implied Volatility Skew</span>
                <Badge variant="outline">Live</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  IV Skew shows how implied volatility varies across different strikes. A volatility smile indicates market expectations of extreme moves.
                </div>
                
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={getIVSkewData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="strike" />
                      <YAxis />
                      <Tooltip 
                        formatter={(value, name) => [
                          `${Number(value).toFixed(2)}%`,
                          name === 'callIV' ? 'Call IV' : 'Put IV'
                        ]}
                      />
                      <Line type="monotone" dataKey="callIV" stroke="#10b981" strokeWidth={2} name="Call IV" />
                      <Line type="monotone" dataKey="putIV" stroke="#ef4444" strokeWidth={2} name="Put IV" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div className="text-center">
                    <div className="font-semibold text-green-600">ATM IV</div>
                    <div>{getIVSkewData().find(d => d.isATM)?.callIV.toFixed(2) || 'N/A'}%</div>
                  </div>
                  <div className="text-center">
                    <div className="font-semibold text-blue-600">OTM Call IV</div>
                    <div>{getIVSkewData().filter(d => d.moneyness > 2).slice(-1)[0]?.callIV.toFixed(2) || 'N/A'}%</div>
                  </div>
                  <div className="text-center">
                    <div className="font-semibold text-red-600">OTM Put IV</div>
                    <div>{getIVSkewData().filter(d => d.moneyness < -2)[0]?.putIV.toFixed(2) || 'N/A'}%</div>
                  </div>
                  <div className="text-center">
                    <div className="font-semibold text-purple-600">Skew Type</div>
                    <div>{getIVSkewData().length > 0 ? 'Forward' : 'N/A'}</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'oi' && (
        <div className="space-y-6">
          {/* Open Interest Analysis */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-blue-600">
                  {getOIAnalysisData().reduce((sum, d) => sum + d.callOI, 0).toLocaleString()}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Total Call OI</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-red-600">
                  {getOIAnalysisData().reduce((sum, d) => sum + d.putOI, 0).toLocaleString()}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Total Put OI</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-purple-600">
                  {getOIAnalysisData().reduce((sum, d) => sum + d.netOI, 0).toLocaleString()}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Net Call-Put OI</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>🔍 Open Interest Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={getOIAnalysisData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="strike" />
                      <YAxis />
                      <Tooltip 
                        formatter={(value, name) => [
                          Number(value).toLocaleString(),
                          name === 'callOI' ? 'Call OI' : 'Put OI'
                        ]}
                      />
                      <Bar dataKey="callOI" fill="#10b981" />
                      <Bar dataKey="putOI" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                
                {/* Unusual Activity */}
                <div className="mt-6">
                  <h4 className="font-semibold mb-3">⚡ Unusual Activity Alerts</h4>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {getUnusualActivity().slice(0, 5).map((activity, idx) => (
                      <div key={idx} className="flex justify-between items-center p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded">
                        <div className="flex items-center space-x-2">
                          <Badge variant={activity.type === 'CALL_HEAVY' ? 'default' : 'destructive'}>
                            {activity.strike}
                          </Badge>
                          <span className="text-sm">
                            {activity.type === 'CALL_HEAVY' ? '📈 Call Heavy' : '📉 Put Heavy'}
                          </span>
                        </div>
                        <div className="text-sm text-gray-600">
                          Vol: {(activity.callVolume + activity.putVolume).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'greeks' && (
        <div className="space-y-6">
          <GreeksHeatmap />
        </div>
      )}

      {activeTab === 'maxpain' && (
        <div className="space-y-6">
          {/* Max Pain Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-orange-600">
                  {maxPainData.maxPainStrike}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Max Pain Strike</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-blue-600">
                  {formatCurrency(optionData.spot_price)}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Current Spot</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <div className={`text-2xl font-bold ${maxPainData.distanceFromSpot > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {maxPainData.distanceFromSpot > 0 ? '+' : ''}{maxPainData.distanceFromSpot}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Distance (Points)</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <div className={`text-2xl font-bold ${maxPainData.distancePercent > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {maxPainData.distancePercent > 0 ? '+' : ''}{maxPainData.distancePercent}%
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Distance (%)</div>
              </CardContent>
            </Card>
          </div>

          {/* Max Pain Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Max Pain Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  <strong>Max Pain Theory:</strong> The strike price where the maximum number of options (both calls and puts) expire worthless, 
                  causing maximum financial loss to option buyers. Market makers often try to pin the price near max pain at expiry.
                </div>
                
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={getMaxPainChartData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="strike" />
                      <YAxis />
                      <Tooltip 
                        formatter={(value) => [
                          `₹${Number(value).toFixed(2)}M`,
                          'Total Pain'
                        ]}
                      />
                      <Bar 
                        dataKey="pain" 
                        fill="#3b82f6"
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                
                <div className="text-xs text-gray-500">
                  * Red bar indicates Max Pain strike. Lower values mean more pain for option writers.
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Last Updated */}
      <div className="text-xs text-gray-500 text-center">
        Last updated: {new Date(optionData.timestamp).toLocaleString('en-IN')}
      </div>
    </div>
  );
};
