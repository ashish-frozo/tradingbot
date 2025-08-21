import React from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  LineChart,
  Line,
  Legend
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { useAppStore } from '../stores/useAppStore';

interface LatencyChartProps {
  className?: string;
}

export const LatencyChart: React.FC<LatencyChartProps> = ({ className = '' }) => {
  const { latencyHistory } = useAppStore();

  // Process latency data into histogram buckets
  const processLatencyHistogram = (data: number[]) => {
    const buckets = [
      { range: '0-25ms', min: 0, max: 25, count: 0 },
      { range: '25-50ms', min: 25, max: 50, count: 0 },
      { range: '50-100ms', min: 50, max: 100, count: 0 },
      { range: '100-150ms', min: 100, max: 150, count: 0 },
      { range: '150-200ms', min: 150, max: 200, count: 0 },
      { range: '200ms+', min: 200, max: Infinity, count: 0 },
    ];

    data.forEach(latency => {
      const bucket = buckets.find(b => latency >= b.min && latency < b.max);
      if (bucket) bucket.count++;
    });

    return buckets;
  };

  // Generate mock slippage data
  const generateMockSlippageData = () => {
    const data = [];
    const now = Date.now();
    
    for (let i = 0; i < 50; i++) {
      const timestamp = new Date(now - (49 - i) * 60000); // 1 minute apart
      const avgSlippage = Math.random() * 0.8 + 0.1; // 0.1 to 0.9 rupees
      const maxSlippage = avgSlippage + Math.random() * 0.5; // Higher than average
      
      data.push({
        time: timestamp.toLocaleTimeString('en-US', { 
          hour: '2-digit', 
          minute: '2-digit' 
        }),
        timestamp: timestamp.toISOString(),
        avgSlippage: Number(avgSlippage.toFixed(2)),
        maxSlippage: Number(maxSlippage.toFixed(2)),
        tradeCount: Math.floor(Math.random() * 10) + 1,
      });
    }
    
    return data;
  };

  const latencyHistogram = processLatencyHistogram(latencyHistory);
  const slippageData = generateMockSlippageData();
  
  // Calculate statistics
  const avgLatency = latencyHistory.length > 0 
    ? latencyHistory.reduce((sum, val) => sum + val, 0) / latencyHistory.length 
    : 0;
  const maxLatency = latencyHistory.length > 0 
    ? Math.max(...latencyHistory) 
    : 0;
  const p95Latency = latencyHistory.length > 0 
    ? latencyHistory.sort((a, b) => a - b)[Math.floor(latencyHistory.length * 0.95)] 
    : 0;

  const avgSlippage = slippageData.length > 0 
    ? slippageData.reduce((sum, val) => sum + val.avgSlippage, 0) / slippageData.length 
    : 0;
  const maxSlippageValue = slippageData.length > 0 
    ? Math.max(...slippageData.map(d => d.maxSlippage)) 
    : 0;

  const getLatencyStatus = (latency: number) => {
    if (latency < 50) return { color: 'bg-green-500', text: 'Excellent', variant: 'default' as const };
    if (latency < 100) return { color: 'bg-yellow-500', text: 'Good', variant: 'secondary' as const };
    if (latency < 150) return { color: 'bg-orange-500', text: 'Acceptable', variant: 'secondary' as const };
    return { color: 'bg-red-500', text: 'Poor', variant: 'destructive' as const };
  };

  const getSlippageStatus = (slippage: number) => {
    if (slippage < 0.3) return { color: 'bg-green-500', text: 'Low', variant: 'default' as const };
    if (slippage < 0.6) return { color: 'bg-yellow-500', text: 'Medium', variant: 'secondary' as const };
    return { color: 'bg-red-500', text: 'High', variant: 'destructive' as const };
  };

  const latencyStatus = getLatencyStatus(avgLatency);
  const slippageStatus = getSlippageStatus(avgSlippage);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Performance Metrics Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Execution Performance Metrics</span>
            <div className="flex items-center space-x-2">
              <Badge variant={latencyStatus.variant}>
                Latency: {latencyStatus.text}
              </Badge>
              <Badge variant={slippageStatus.variant}>
                Slippage: {slippageStatus.text}
              </Badge>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {avgLatency.toFixed(1)}ms
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Avg Latency
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                {p95Latency.toFixed(1)}ms
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                95th Percentile
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                ₹{avgSlippage.toFixed(2)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Avg Slippage
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                ₹{maxSlippageValue.toFixed(2)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Max Slippage
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latency Histogram */}
        <Card>
          <CardHeader>
            <CardTitle>Latency Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={latencyHistogram}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="range" 
                    fontSize={12}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis fontSize={12} />
                  <Tooltip 
                    formatter={(value) => [`${value} trades`, 'Count']}
                    labelFormatter={(label) => `Latency: ${label}`}
                  />
                  <Bar 
                    dataKey="count" 
                    fill="#3b82f6"
                    radius={[2, 2, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            
            {/* Latency Targets */}
            <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center justify-between">
                <span>Target: &lt;150ms</span>
                <span className={avgLatency < 150 ? 'text-green-600' : 'text-red-600'}>
                  {avgLatency < 150 ? '✅ Met' : '❌ Missed'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Samples: {latencyHistory.length}</span>
                <span>Max: {maxLatency.toFixed(1)}ms</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Slippage Tracking */}
        <Card>
          <CardHeader>
            <CardTitle>Slippage Tracking (Last Hour)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={slippageData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="time" 
                    fontSize={12}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis 
                    fontSize={12}
                    domain={[0, 'dataMax + 0.2']}
                    tickFormatter={(value) => `₹${value.toFixed(1)}`}
                  />
                  <Tooltip 
                    formatter={(value, name) => [
                      `₹${Number(value).toFixed(2)}`, 
                      name === 'avgSlippage' ? 'Avg Slippage' : 'Max Slippage'
                    ]}
                    labelFormatter={(label) => `Time: ${label}`}
                  />
                  <Legend />
                  <Line 
                    type="monotone" 
                    dataKey="avgSlippage" 
                    stroke="#10b981" 
                    strokeWidth={2}
                    dot={{ r: 2 }}
                    name="Avg Slippage"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="maxSlippage" 
                    stroke="#ef4444" 
                    strokeWidth={2}
                    dot={{ r: 2 }}
                    name="Max Slippage"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            
            {/* Slippage Targets */}
            <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center justify-between">
                <span>Target: &lt;₹0.30</span>
                <span className={avgSlippage < 0.3 ? 'text-green-600' : 'text-red-600'}>
                  {avgSlippage < 0.3 ? '✅ Met' : '❌ Missed'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Reject Threshold: &gt;₹0.30</span>
                <span className="text-blue-600">
                  {slippageData.filter(d => d.maxSlippage > 0.3).length} violations
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Performance Alerts */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {avgLatency > 150 && (
              <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <span className="text-red-500">⚠️</span>
                <span className="text-red-700 dark:text-red-300 font-medium">
                  High average latency: {avgLatency.toFixed(1)}ms - Target is &lt;150ms
                </span>
              </div>
            )}
            
            {p95Latency > 200 && (
              <div className="flex items-center space-x-2 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800">
                <span className="text-orange-500">⚡</span>
                <span className="text-orange-700 dark:text-orange-300 font-medium">
                  High 95th percentile latency: {p95Latency.toFixed(1)}ms - May impact execution
                </span>
              </div>
            )}
            
            {avgSlippage > 0.3 && (
              <div className="flex items-center space-x-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                <span className="text-yellow-500">💰</span>
                <span className="text-yellow-700 dark:text-yellow-300 font-medium">
                  High average slippage: ₹{avgSlippage.toFixed(2)} - Consider adjusting order strategy
                </span>
              </div>
            )}
            
            {maxSlippageValue > 1.0 && (
              <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <span className="text-red-500">🚨</span>
                <span className="text-red-700 dark:text-red-300 font-medium">
                  Excessive slippage detected: ₹{maxSlippageValue.toFixed(2)} - Review market conditions
                </span>
              </div>
            )}
            
            {avgLatency < 100 && avgSlippage < 0.3 && (
              <div className="flex items-center space-x-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <span className="text-green-500">✅</span>
                <span className="text-green-700 dark:text-green-300 font-medium">
                  Excellent execution performance - Both latency and slippage within targets
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default LatencyChart; 