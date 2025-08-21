import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar } from 'recharts';

interface StrategyPnLData {
  timestamp: string;
  pnl: number;
  cumulativePnl: number;
  drawdown: number;
  positions: number;
}

interface StrategyMetrics {
  totalPnL: number;
  winRate: number;
  profitFactor: number;
  maxDrawdown: number;
  sharpeRatio: number;
  totalTrades: number;
  avgWin: number;
  avgLoss: number;
}

interface Strategy {
  id: string;
  name: string;
  status: string;
  pnlData: StrategyPnLData[];
  metrics: StrategyMetrics;
}

export const StrategyPnLVisualizer: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('all');
  const [timeframe, setTimeframe] = useState<'1D' | '1W' | '1M' | '3M'>('1D');
  const [viewType, setViewType] = useState<'pnl' | 'drawdown' | 'positions'>('pnl');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStrategyData();
    const interval = setInterval(fetchStrategyData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchStrategyData = async () => {
    try {
      // Mock data - in real implementation, fetch from backend
      const mockStrategies: Strategy[] = [
        {
          id: 'iron-condor',
          name: 'Iron Condor',
          status: 'ACTIVE',
          pnlData: generateMockPnLData('iron-condor'),
          metrics: {
            totalPnL: 15750,
            winRate: 72,
            profitFactor: 1.85,
            maxDrawdown: -8500,
            sharpeRatio: 1.42,
            totalTrades: 45,
            avgWin: 850,
            avgLoss: -450
          }
        },
        {
          id: 'straddle',
          name: 'Short Straddle',
          status: 'ACTIVE',
          pnlData: generateMockPnLData('straddle'),
          metrics: {
            totalPnL: -2300,
            winRate: 65,
            profitFactor: 0.85,
            maxDrawdown: -12000,
            sharpeRatio: 0.65,
            totalTrades: 28,
            avgWin: 650,
            avgLoss: -750
          }
        },
        {
          id: 'butterfly',
          name: 'Butterfly Spread',
          status: 'PAUSED',
          pnlData: generateMockPnLData('butterfly'),
          metrics: {
            totalPnL: 8900,
            winRate: 68,
            profitFactor: 1.35,
            maxDrawdown: -5200,
            sharpeRatio: 1.15,
            totalTrades: 32,
            avgWin: 420,
            avgLoss: -280
          }
        }
      ];
      
      setStrategies(mockStrategies);
    } catch (error) {
      console.error('Error fetching strategy data:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateMockPnLData = (strategyType: string): StrategyPnLData[] => {
    const data: StrategyPnLData[] = [];
    let cumulativePnL = 0;
    let maxPnL = 0;
    
    for (let i = 0; i < 30; i++) {
      const date = new Date();
      date.setDate(date.getDate() - (29 - i));
      
      let dailyPnL = 0;
      switch (strategyType) {
        case 'iron-condor':
          dailyPnL = (Math.random() - 0.3) * 1000;
          break;
        case 'straddle':
          dailyPnL = (Math.random() - 0.45) * 800;
          break;
        case 'butterfly':
          dailyPnL = (Math.random() - 0.35) * 600;
          break;
      }
      
      cumulativePnL += dailyPnL;
      maxPnL = Math.max(maxPnL, cumulativePnL);
      const drawdown = cumulativePnL - maxPnL;
      
      data.push({
        timestamp: date.toISOString().split('T')[0],
        pnl: dailyPnL,
        cumulativePnl: cumulativePnL,
        drawdown: drawdown,
        positions: Math.floor(Math.random() * 8) + 2
      });
    }
    
    return data;
  };

  const getChartData = () => {
    if (selectedStrategy === 'all') {
      // Combine all strategies
      const combinedData: { [key: string]: StrategyPnLData } = {};
      
      strategies.forEach(strategy => {
        strategy.pnlData.forEach(point => {
          if (!combinedData[point.timestamp]) {
            combinedData[point.timestamp] = {
              timestamp: point.timestamp,
              pnl: 0,
              cumulativePnl: 0,
              drawdown: 0,
              positions: 0
            };
          }
          combinedData[point.timestamp].pnl += point.pnl;
          combinedData[point.timestamp].cumulativePnl += point.cumulativePnl;
          combinedData[point.timestamp].drawdown += point.drawdown;
          combinedData[point.timestamp].positions += point.positions;
        });
      });
      
      return Object.values(combinedData).sort((a, b) => 
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
    } else {
      const strategy = strategies.find(s => s.id === selectedStrategy);
      return strategy?.pnlData || [];
    }
  };

  const getCombinedMetrics = (): StrategyMetrics => {
    if (selectedStrategy === 'all') {
      return {
        totalPnL: strategies.reduce((sum, s) => sum + s.metrics.totalPnL, 0),
        winRate: strategies.reduce((sum, s) => sum + s.metrics.winRate, 0) / strategies.length,
        profitFactor: strategies.reduce((sum, s) => sum + s.metrics.profitFactor, 0) / strategies.length,
        maxDrawdown: Math.min(...strategies.map(s => s.metrics.maxDrawdown)),
        sharpeRatio: strategies.reduce((sum, s) => sum + s.metrics.sharpeRatio, 0) / strategies.length,
        totalTrades: strategies.reduce((sum, s) => sum + s.metrics.totalTrades, 0),
        avgWin: strategies.reduce((sum, s) => sum + s.metrics.avgWin, 0) / strategies.length,
        avgLoss: strategies.reduce((sum, s) => sum + s.metrics.avgLoss, 0) / strategies.length
      };
    } else {
      const strategy = strategies.find(s => s.id === selectedStrategy);
      return strategy?.metrics || {
        totalPnL: 0, winRate: 0, profitFactor: 0, maxDrawdown: 0,
        sharpeRatio: 0, totalTrades: 0, avgWin: 0, avgLoss: 0
      };
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center">Loading strategy P&L data...</div>
        </CardContent>
      </Card>
    );
  }

  const chartData = getChartData();
  const metrics = getCombinedMetrics();

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex space-x-2">
          <select 
            value={selectedStrategy}
            onChange={(e) => setSelectedStrategy(e.target.value)}
            className="px-3 py-1 border rounded text-sm"
          >
            <option value="all">All Strategies</option>
            {strategies.map(strategy => (
              <option key={strategy.id} value={strategy.id}>
                {strategy.name}
              </option>
            ))}
          </select>
        </div>
        
        <div className="flex space-x-2">
          {(['1D', '1W', '1M', '3M'] as const).map(tf => (
            <Button
              key={tf}
              variant={timeframe === tf ? 'default' : 'outline'}
              size="sm"
              onClick={() => setTimeframe(tf)}
            >
              {tf}
            </Button>
          ))}
        </div>
        
        <div className="flex space-x-2">
          {(['pnl', 'drawdown', 'positions'] as const).map(vt => (
            <Button
              key={vt}
              variant={viewType === vt ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewType(vt)}
            >
              {vt === 'pnl' ? '💰 P&L' : vt === 'drawdown' ? '📉 Drawdown' : '📊 Positions'}
            </Button>
          ))}
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
        <Card>
          <CardContent className="p-3">
            <div className={`text-lg font-bold ${metrics.totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ₹{metrics.totalPnL.toLocaleString()}
            </div>
            <div className="text-xs text-gray-600">Total P&L</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3">
            <div className="text-lg font-bold text-blue-600">
              {metrics.winRate.toFixed(1)}%
            </div>
            <div className="text-xs text-gray-600">Win Rate</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3">
            <div className={`text-lg font-bold ${metrics.profitFactor >= 1 ? 'text-green-600' : 'text-red-600'}`}>
              {metrics.profitFactor.toFixed(2)}
            </div>
            <div className="text-xs text-gray-600">Profit Factor</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3">
            <div className="text-lg font-bold text-red-600">
              ₹{metrics.maxDrawdown.toLocaleString()}
            </div>
            <div className="text-xs text-gray-600">Max Drawdown</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3">
            <div className="text-lg font-bold text-purple-600">
              {metrics.sharpeRatio.toFixed(2)}
            </div>
            <div className="text-xs text-gray-600">Sharpe Ratio</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3">
            <div className="text-lg font-bold text-gray-600">
              {metrics.totalTrades}
            </div>
            <div className="text-xs text-gray-600">Total Trades</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3">
            <div className="text-lg font-bold text-green-600">
              ₹{metrics.avgWin.toFixed(0)}
            </div>
            <div className="text-xs text-gray-600">Avg Win</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3">
            <div className="text-lg font-bold text-red-600">
              ₹{metrics.avgLoss.toFixed(0)}
            </div>
            <div className="text-xs text-gray-600">Avg Loss</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>
              {viewType === 'pnl' ? '💰 P&L Evolution' : 
               viewType === 'drawdown' ? '📉 Drawdown Analysis' : '📊 Position Count'}
            </span>
            <Badge variant="outline">Live</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              {viewType === 'pnl' ? (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="timestamp" />
                  <YAxis />
                  <Tooltip 
                    formatter={(value) => [
                      `₹${Number(value).toLocaleString()}`,
                      'Cumulative P&L'
                    ]}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="cumulativePnl" 
                    stroke="#3b82f6" 
                    fill="#3b82f6"
                    fillOpacity={0.3}
                  />
                </AreaChart>
              ) : viewType === 'drawdown' ? (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="timestamp" />
                  <YAxis />
                  <Tooltip 
                    formatter={(value) => [
                      `₹${Number(value).toLocaleString()}`,
                      'Drawdown'
                    ]}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="drawdown" 
                    stroke="#ef4444" 
                    fill="#ef4444"
                    fillOpacity={0.3}
                  />
                </AreaChart>
              ) : (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="timestamp" />
                  <YAxis />
                  <Tooltip 
                    formatter={(value) => [
                      Number(value),
                      'Active Positions'
                    ]}
                  />
                  <Bar dataKey="positions" fill="#10b981" />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Strategy Performance Table */}
      <Card>
        <CardHeader>
          <CardTitle>📊 Strategy Performance Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Strategy</th>
                  <th className="text-center p-2">Status</th>
                  <th className="text-center p-2">Total P&L</th>
                  <th className="text-center p-2">Win Rate</th>
                  <th className="text-center p-2">Profit Factor</th>
                  <th className="text-center p-2">Max DD</th>
                  <th className="text-center p-2">Sharpe</th>
                  <th className="text-center p-2">Trades</th>
                </tr>
              </thead>
              <tbody>
                {strategies.map((strategy) => (
                  <tr key={strategy.id} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="p-2 font-medium">{strategy.name}</td>
                    <td className="text-center p-2">
                      <Badge variant={strategy.status === 'ACTIVE' ? 'default' : 'secondary'}>
                        {strategy.status}
                      </Badge>
                    </td>
                    <td className={`text-center p-2 font-mono ${strategy.metrics.totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ₹{strategy.metrics.totalPnL.toLocaleString()}
                    </td>
                    <td className="text-center p-2 font-mono">{strategy.metrics.winRate.toFixed(1)}%</td>
                    <td className={`text-center p-2 font-mono ${strategy.metrics.profitFactor >= 1 ? 'text-green-600' : 'text-red-600'}`}>
                      {strategy.metrics.profitFactor.toFixed(2)}
                    </td>
                    <td className="text-center p-2 font-mono text-red-600">
                      ₹{strategy.metrics.maxDrawdown.toLocaleString()}
                    </td>
                    <td className="text-center p-2 font-mono">{strategy.metrics.sharpeRatio.toFixed(2)}</td>
                    <td className="text-center p-2">{strategy.metrics.totalTrades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default StrategyPnLVisualizer;
