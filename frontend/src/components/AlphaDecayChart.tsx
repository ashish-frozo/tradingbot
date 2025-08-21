import React from 'react';
import { 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  LineChart,
  Line,
  ReferenceLine
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { useAppStore } from '../stores/useAppStore';
import { formatCurrency } from '../lib/utils';

interface AlphaDecayChartProps {
  className?: string;
}

export const AlphaDecayChart: React.FC<AlphaDecayChartProps> = ({ className = '' }) => {
  const { positions } = useAppStore();

  // Generate mock alpha decay data
  const generateMockAlphaDecayData = () => {
    const data = [];
    const now = Date.now();
    
    // Generate historical trade data
    for (let i = 0; i < 200; i++) {
      const ageMinutes = Math.random() * 600; // 0 to 10 hours in minutes
      const baseAlpha = Math.max(0, 1000 - (ageMinutes * 2)); // Decay over time
      const noise = (Math.random() - 0.5) * 500; // Random noise
      const pnl = baseAlpha + noise;
      
      data.push({
        ageMinutes: Number(ageMinutes.toFixed(1)),
        pnl: Number(pnl.toFixed(2)),
        symbol: `NIFTY_${Math.floor(Math.random() * 5) + 1}`,
        size: Math.random() * 20 + 5, // For scatter plot sizing
      });
    }
    
    return data.sort((a, b) => a.ageMinutes - b.ageMinutes);
  };

  // Calculate current positions age and P&L
  const getCurrentPositionsData = () => {
    return positions.map(pos => {
      const entryTime = new Date(pos.entry_time).getTime();
      const ageMinutes = (Date.now() - entryTime) / (1000 * 60);
      
      return {
        ageMinutes: Number(ageMinutes.toFixed(1)),
        pnl: pos.unrealized_pnl,
        symbol: pos.symbol,
        size: Math.abs(pos.quantity),
        isCurrentPosition: true,
      };
    });
  };

  // Generate trend line data
  const generateTrendLineData = (data: any[]) => {
    const buckets = [];
    const bucketSize = 30; // 30-minute buckets
    const maxAge = Math.max(...data.map(d => d.ageMinutes));
    
    for (let i = 0; i <= maxAge; i += bucketSize) {
      const bucketData = data.filter(d => d.ageMinutes >= i && d.ageMinutes < i + bucketSize);
      if (bucketData.length > 0) {
        const avgPnl = bucketData.reduce((sum, d) => sum + d.pnl, 0) / bucketData.length;
        buckets.push({
          ageMinutes: i + bucketSize / 2,
          avgPnl: Number(avgPnl.toFixed(2)),
        });
      }
    }
    
    return buckets;
  };

  const mockData = generateMockAlphaDecayData();
  const currentPositionsData = getCurrentPositionsData();
  const allData = [...mockData, ...currentPositionsData];
  const trendLineData = generateTrendLineData(mockData);

  // Calculate statistics
  const calculateAlphaDecayRate = () => {
    if (trendLineData.length < 2) return 0;
    const firstPoint = trendLineData[0];
    const lastPoint = trendLineData[trendLineData.length - 1];
    const timeSpan = lastPoint.ageMinutes - firstPoint.ageMinutes;
    const pnlChange = lastPoint.avgPnl - firstPoint.avgPnl;
    return timeSpan > 0 ? (pnlChange / timeSpan) : 0;
  };

  const avgInitialAlpha = trendLineData.length > 0 ? trendLineData[0]?.avgPnl || 0 : 0;
  const currentAlpha = trendLineData.length > 0 ? trendLineData[trendLineData.length - 1]?.avgPnl || 0 : 0;
  const decayRate = calculateAlphaDecayRate();
  const halfLife = Math.abs(decayRate) > 0.1 ? Math.abs(avgInitialAlpha / (2 * decayRate)) : Infinity;

  const getDecayStatus = (rate: number) => {
    if (rate > -1) return { text: 'Stable', variant: 'default' as const, color: 'text-green-600' };
    if (rate > -3) return { text: 'Moderate Decay', variant: 'secondary' as const, color: 'text-yellow-600' };
    return { text: 'Fast Decay', variant: 'destructive' as const, color: 'text-red-600' };
  };

  const decayStatus = getDecayStatus(decayRate);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Alpha Decay Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Alpha Decay Analysis</span>
            <Badge variant={decayStatus.variant}>
              {decayStatus.text}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {formatCurrency(avgInitialAlpha)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Initial Alpha
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                {formatCurrency(currentAlpha)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Current Alpha
              </div>
            </div>
            
            <div className="text-center">
              <div className={`text-2xl font-bold ${decayStatus.color}`}>
                {decayRate.toFixed(2)}/min
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Decay Rate
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {halfLife === Infinity ? '∞' : `${halfLife.toFixed(0)}min`}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Half Life
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Alpha Decay Scatter Plot */}
        <Card>
          <CardHeader>
            <CardTitle>P&L vs Position Age (Scatter)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart data={allData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    type="number"
                    dataKey="ageMinutes"
                    name="Age (minutes)"
                    fontSize={12}
                    tickFormatter={(value) => `${value}m`}
                  />
                  <YAxis 
                    type="number"
                    dataKey="pnl"
                    name="P&L"
                    fontSize={12}
                    tickFormatter={(value) => formatCurrency(value)}
                  />
                  <Tooltip 
                    cursor={{ strokeDasharray: '3 3' }}
                    formatter={(value, name) => [
                      name === 'pnl' ? formatCurrency(Number(value)) : value,
                      name === 'pnl' ? 'P&L' : 'Age'
                    ]}
                    labelFormatter={() => ''}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-white dark:bg-gray-800 p-3 border rounded shadow">
                            <p className="font-medium">{data.symbol}</p>
                            <p className="text-sm">Age: {data.ageMinutes}min</p>
                            <p className="text-sm">P&L: {formatCurrency(data.pnl)}</p>
                            <p className="text-sm">Size: {data.size} lots</p>
                            {data.isCurrentPosition && (
                              <p className="text-xs text-blue-600">Current Position</p>
                            )}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Scatter 
                    dataKey="pnl" 
                    fill="#8884d8"
                    fillOpacity={0.6}
                    r={3}
                  />
                  {/* Highlight current positions */}
                  <Scatter 
                    data={currentPositionsData}
                    dataKey="pnl" 
                    fill="#ef4444"
                    r={5}
                  />
                  <ReferenceLine y={0} stroke="#666" strokeDasharray="2 2" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Alpha Decay Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Alpha Decay Trend (30min buckets)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendLineData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="ageMinutes"
                    fontSize={12}
                    tickFormatter={(value) => `${value}m`}
                  />
                  <YAxis 
                    fontSize={12}
                    tickFormatter={(value) => formatCurrency(value)}
                  />
                  <Tooltip 
                    formatter={(value) => [formatCurrency(Number(value)), 'Avg P&L']}
                    labelFormatter={(label) => `Age: ${label}min`}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="avgPnl" 
                    stroke="#8884d8" 
                    strokeWidth={3}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                  <ReferenceLine y={0} stroke="#666" strokeDasharray="2 2" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            
            {/* Decay Analysis */}
            <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center justify-between">
                <span>Optimal Hold Time:</span>
                <span className="font-medium">
                  {halfLife === Infinity ? 'No clear decay' : `~${Math.min(halfLife, 600).toFixed(0)} minutes`}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Current Positions:</span>
                <span className="font-medium text-blue-600">
                  {currentPositionsData.length} active
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Alpha Decay Insights */}
      <Card>
        <CardHeader>
          <CardTitle>Alpha Decay Insights & Recommendations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {decayRate < -3 && (
              <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <span className="text-red-500">⚠️</span>
                <span className="text-red-700 dark:text-red-300 font-medium">
                  Fast alpha decay detected: {decayRate.toFixed(2)}/min - Consider shorter hold times
                </span>
              </div>
            )}
            
            {halfLife < 120 && halfLife !== Infinity && (
              <div className="flex items-center space-x-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                <span className="text-yellow-500">⏰</span>
                <span className="text-yellow-700 dark:text-yellow-300 font-medium">
                  Short alpha half-life: {halfLife.toFixed(0)} minutes - Quick exits may be optimal
                </span>
              </div>
            )}
            
            {currentPositionsData.some(pos => pos.ageMinutes > halfLife && halfLife !== Infinity) && (
              <div className="flex items-center space-x-2 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800">
                <span className="text-orange-500">📊</span>
                <span className="text-orange-700 dark:text-orange-300 font-medium">
                  Some positions exceed optimal hold time - Consider taking profits
                </span>
              </div>
            )}
            
            {avgInitialAlpha > 500 && currentAlpha > 300 && (
              <div className="flex items-center space-x-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <span className="text-green-500">✅</span>
                <span className="text-green-700 dark:text-green-300 font-medium">
                  Strong alpha generation with sustainable decay rate - Strategy performing well
                </span>
              </div>
            )}
            
            {Math.abs(decayRate) < 1 && (
              <div className="flex items-center space-x-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <span className="text-blue-500">📈</span>
                <span className="text-blue-700 dark:text-blue-300 font-medium">
                  Stable alpha profile - No significant decay detected, consider longer hold times
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AlphaDecayChart; 