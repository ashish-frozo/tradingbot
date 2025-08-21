import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

interface VolatilityData {
  expiry: string;
  daysToExpiry: number;
  atmIV: number;
  skew: number;
  term: number;
}

export const VolatilityTermStructure: React.FC = () => {
  const [volatilityData, setVolatilityData] = useState<VolatilityData[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewType, setViewType] = useState<'term' | 'skew'>('term');

  useEffect(() => {
    fetchVolatilityData();
    const interval = setInterval(fetchVolatilityData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchVolatilityData = async () => {
    try {
      // Mock data - in real implementation, this would fetch from backend
      const mockData: VolatilityData[] = [
        { expiry: 'Weekly', daysToExpiry: 3, atmIV: 18.5, skew: -2.1, term: 0.1 },
        { expiry: 'Current', daysToExpiry: 10, atmIV: 16.8, skew: -1.8, term: 0.3 },
        { expiry: 'Next', daysToExpiry: 38, atmIV: 15.2, skew: -1.5, term: 1.0 },
        { expiry: 'Far', daysToExpiry: 66, atmIV: 14.8, skew: -1.2, term: 1.8 },
        { expiry: 'Quarterly', daysToExpiry: 94, atmIV: 14.5, skew: -1.0, term: 2.6 }
      ];
      
      setVolatilityData(mockData);
    } catch (error) {
      console.error('Error fetching volatility data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getVolatilityTrend = () => {
    if (volatilityData.length < 2) return 'FLAT';
    
    const shortTerm = volatilityData[0]?.atmIV || 0;
    const longTerm = volatilityData[volatilityData.length - 1]?.atmIV || 0;
    
    if (shortTerm > longTerm + 1) return 'BACKWARDATION';
    if (longTerm > shortTerm + 1) return 'CONTANGO';
    return 'FLAT';
  };

  const getTrendColor = (trend: string) => {
    switch (trend) {
      case 'BACKWARDATION': return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-200';
      case 'CONTANGO': return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-200';
      default: return 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  const getTrendDescription = (trend: string) => {
    switch (trend) {
      case 'BACKWARDATION':
        return 'Short-term volatility higher than long-term. Market expects near-term uncertainty.';
      case 'CONTANGO':
        return 'Long-term volatility higher than short-term. Normal market structure.';
      default:
        return 'Volatility relatively flat across terms. Stable market conditions.';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center">Loading volatility data...</div>
        </CardContent>
      </Card>
    );
  }

  const trend = getVolatilityTrend();

  return (
    <div className="space-y-6">
      {/* View Toggle */}
      <div className="flex space-x-2">
        <Button
          variant={viewType === 'term' ? 'default' : 'outline'}
          onClick={() => setViewType('term')}
        >
          📈 Term Structure
        </Button>
        <Button
          variant={viewType === 'skew' ? 'default' : 'outline'}
          onClick={() => setViewType('skew')}
        >
          📊 Volatility Skew
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-blue-600">
              {volatilityData[0]?.atmIV.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Front Month IV</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-purple-600">
              {volatilityData[volatilityData.length - 1]?.atmIV.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Back Month IV</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-orange-600">
              {((volatilityData[volatilityData.length - 1]?.atmIV || 0) - (volatilityData[0]?.atmIV || 0)).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Term Spread</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className={`text-sm font-semibold px-2 py-1 rounded ${getTrendColor(trend)}`}>
              {trend}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Market Structure</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>
              {viewType === 'term' ? '📈 Volatility Term Structure' : '📊 Volatility Skew by Expiry'}
            </span>
            <Badge variant="outline">Live</Badge>
          </CardTitle>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {viewType === 'term' 
              ? getTrendDescription(trend)
              : 'Volatility skew shows the difference between OTM put and call implied volatilities.'
            }
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              {viewType === 'term' ? (
                <LineChart data={volatilityData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="expiry" />
                  <YAxis domain={['dataMin - 1', 'dataMax + 1']} />
                  <Tooltip 
                    formatter={(value) => [
                      `${Number(value).toFixed(2)}%`,
                      'ATM IV'
                    ]}
                    labelFormatter={(label) => `${label} Expiry`}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="atmIV" 
                    stroke="#3b82f6" 
                    strokeWidth={3}
                    dot={{ fill: '#3b82f6', strokeWidth: 2, r: 6 }}
                    activeDot={{ r: 8, stroke: '#3b82f6', strokeWidth: 2 }}
                  />
                </LineChart>
              ) : (
                <BarChart data={volatilityData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="expiry" />
                  <YAxis />
                  <Tooltip 
                    formatter={(value) => [
                      `${Number(value).toFixed(2)}%`,
                      'Volatility Skew'
                    ]}
                  />
                  <Bar 
                    dataKey="skew" 
                    fill="#ef4444"
                    name="Volatility Skew"
                  />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Table */}
      <Card>
        <CardHeader>
          <CardTitle>📋 Volatility Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Expiry</th>
                  <th className="text-center p-2">Days to Expiry</th>
                  <th className="text-center p-2">ATM IV</th>
                  <th className="text-center p-2">Volatility Skew</th>
                  <th className="text-center p-2">Term</th>
                  <th className="text-center p-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {volatilityData.map((row, index) => (
                  <tr key={index} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="p-2 font-medium">{row.expiry}</td>
                    <td className="text-center p-2">{row.daysToExpiry}</td>
                    <td className="text-center p-2 font-mono">{row.atmIV.toFixed(2)}%</td>
                    <td className={`text-center p-2 font-mono ${row.skew < 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {row.skew.toFixed(2)}%
                    </td>
                    <td className="text-center p-2 font-mono">{row.term.toFixed(1)}</td>
                    <td className="text-center p-2">
                      <Badge variant={row.atmIV > 16 ? 'destructive' : row.atmIV < 14 ? 'default' : 'secondary'}>
                        {row.atmIV > 16 ? 'High' : row.atmIV < 14 ? 'Low' : 'Normal'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Trading Insights */}
      <Card>
        <CardHeader>
          <CardTitle>💡 Trading Insights</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h4 className="font-semibold text-green-600">Opportunities</h4>
              <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
                {trend === 'BACKWARDATION' && (
                  <>
                    <li>• Consider selling front-month options (high IV)</li>
                    <li>• Calendar spreads may be profitable</li>
                    <li>• Short-term volatility likely to decrease</li>
                  </>
                )}
                {trend === 'CONTANGO' && (
                  <>
                    <li>• Normal market structure - standard strategies work</li>
                    <li>• Long volatility in front months</li>
                    <li>• Time decay strategies effective</li>
                  </>
                )}
                {trend === 'FLAT' && (
                  <>
                    <li>• Stable volatility environment</li>
                    <li>• Focus on directional strategies</li>
                    <li>• Limited volatility arbitrage opportunities</li>
                  </>
                )}
              </ul>
            </div>
            <div className="space-y-2">
              <h4 className="font-semibold text-red-600">Risks</h4>
              <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
                <li>• Volatility term structure can change rapidly</li>
                <li>• Event risk may spike short-term volatility</li>
                <li>• Liquidity may be lower in far-dated options</li>
                <li>• Greeks exposure increases with volatility changes</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default VolatilityTermStructure;
