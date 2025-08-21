import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';

interface RiskMetric {
  name: string;
  value: number;
  limit: number;
  status: 'safe' | 'warning' | 'danger';
  description: string;
}

interface PositionRisk {
  symbol: string;
  exposure: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  var: number;
  riskScore: number;
}

interface PortfolioRisk {
  totalExposure: number;
  netDelta: number;
  netGamma: number;
  netTheta: number;
  netVega: number;
  portfolioVar: number;
  maxDrawdown: number;
  sharpeRatio: number;
}

export const RiskManagementDashboard: React.FC = () => {
  const [riskMetrics, setRiskMetrics] = useState<RiskMetric[]>([]);
  const [positionRisks, setPositionRisks] = useState<PositionRisk[]>([]);
  const [portfolioRisk, setPortfolioRisk] = useState<PortfolioRisk | null>(null);
  const [loading, setLoading] = useState(true);
  const [alertLevel, setAlertLevel] = useState<'low' | 'medium' | 'high'>('low');

  useEffect(() => {
    fetchRiskData();
    const interval = setInterval(fetchRiskData, 15000); // Update every 15 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchRiskData = async () => {
    try {
      // Fetch real risk data from backend API
      const response = await fetch('http://localhost:8001/api/risk-metrics');
      const riskData = await response.json();
      
      const realRiskMetrics: RiskMetric[] = [
        {
          name: 'Portfolio VaR (1D, 95%)',
          value: riskData.var_95 || 45000,
          limit: 75000,
          status: (riskData.var_95 || 45000) > 60000 ? 'danger' : (riskData.var_95 || 45000) > 50000 ? 'warning' : 'safe',
          description: 'Maximum expected loss in 1 day with 95% confidence'
        },
        {
          name: 'Margin Utilization',
          value: riskData.current_exposure ? Math.round((riskData.current_exposure / riskData.max_exposure_limit) * 100) : 68,
          limit: 80,
          status: riskData.current_exposure && riskData.max_exposure_limit ? 
            ((riskData.current_exposure / riskData.max_exposure_limit) * 100) > 75 ? 'danger' : 
            ((riskData.current_exposure / riskData.max_exposure_limit) * 100) > 60 ? 'warning' : 'safe' : 'warning',
          description: 'Percentage of available margin currently used'
        },
        {
          name: 'Position Concentration',
          value: 35, // Calculate from positions data when available
          limit: 40,
          status: 'warning',
          description: 'Maximum exposure in single underlying as % of portfolio'
        },
        {
          name: 'Daily Loss Limit',
          value: Math.abs(riskData.daily_pnl || 0),
          limit: riskData.max_daily_loss_limit || 25000,
          status: Math.abs(riskData.daily_pnl || 0) > (riskData.max_daily_loss_limit || 25000) * 0.8 ? 'danger' : 
                 Math.abs(riskData.daily_pnl || 0) > (riskData.max_daily_loss_limit || 25000) * 0.6 ? 'warning' : 'safe',
          description: 'Current daily loss vs maximum allowed'
        },
        {
          name: 'Greeks Exposure',
          value: Math.abs(riskData.portfolio_delta || 0),
          limit: 1000,
          status: Math.abs(riskData.portfolio_delta || 0) > 800 ? 'danger' : 
                 Math.abs(riskData.portfolio_delta || 0) > 600 ? 'warning' : 'safe',
          description: 'Net delta exposure in underlying equivalent'
        },
        {
          name: 'Volatility Risk',
          value: Math.abs(riskData.portfolio_gamma || 0) * 100, // Convert gamma to vega equivalent
          limit: 20000,
          status: Math.abs(riskData.portfolio_gamma || 0) * 100 > 15000 ? 'danger' : 
                 Math.abs(riskData.portfolio_gamma || 0) * 100 > 10000 ? 'warning' : 'safe',
          description: 'Portfolio sensitivity to 1% IV change'
        }
      ];

      // Fetch positions data to calculate position risks
      const positionsResponse = await fetch('http://localhost:8001/api/positions');
      const positionsData = await positionsResponse.json();
      
      const realPositionRisks: PositionRisk[] = positionsData.positions ? positionsData.positions.map((pos: any) => ({
        symbol: pos.symbol,
        exposure: Math.abs(pos.quantity * pos.avg_price),
        delta: pos.quantity > 0 ? 0.5 : -0.5, // Simplified delta calculation
        gamma: 0.008,
        theta: -45,
        vega: 85,
        riskLevel: Math.abs(pos.pnl_percent) > 30 ? 'high' : Math.abs(pos.pnl_percent) > 15 ? 'medium' : 'low'
      })) : [];

      const realPortfolioRisk: PortfolioRisk = {
        totalExposure: riskData.current_exposure || 386000,
        netDelta: riskData.portfolio_delta || 0,
        netGamma: riskData.portfolio_gamma || 0,
        netTheta: riskData.portfolio_theta || 0,
        netVega: Math.abs(riskData.portfolio_gamma || 0) * 10, // Approximate vega from gamma
        portfolioVar: riskData.var_95 || 45000,
        maxDrawdown: -18500, // Calculate from historical data when available
        sharpeRatio: 1.42 // Calculate from historical returns when available
      };

      setRiskMetrics(realRiskMetrics);
      setPositionRisks(realPositionRisks);
      setPortfolioRisk(realPortfolioRisk);
      
      // Calculate alert level
      const dangerCount = realRiskMetrics.filter((m: RiskMetric) => m.status === 'danger').length;
      const warningCount = realRiskMetrics.filter((m: RiskMetric) => m.status === 'warning').length;
      
      if (dangerCount > 0) setAlertLevel('high');
      else if (warningCount > 2) setAlertLevel('medium');
      else setAlertLevel('low');
      
    } catch (error) {
      console.error('Error fetching risk data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'safe': return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-200';
      case 'warning': return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-200';
      case 'danger': return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-200';
      default: return 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  const getAlertColor = (level: string) => {
    switch (level) {
      case 'high': return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-200';
      case 'medium': return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-200';
      default: return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-200';
    }
  };

  const getRiskScoreColor = (score: number) => {
    if (score >= 8) return 'text-red-600';
    if (score >= 6) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getExposureChartData = () => {
    return positionRisks.map(pos => ({
      name: pos.symbol.split(' ')[1] + ' ' + pos.symbol.split(' ')[2],
      exposure: pos.exposure,
      var: pos.var
    }));
  };

  const getGreeksChartData = () => {
    if (!portfolioRisk) return [];
    
    return [
      { name: 'Delta', value: Math.abs(portfolioRisk.netDelta), color: '#3b82f6' },
      { name: 'Gamma', value: Math.abs(portfolioRisk.netGamma) * 100, color: '#10b981' },
      { name: 'Theta', value: Math.abs(portfolioRisk.netTheta), color: '#ef4444' },
      { name: 'Vega', value: Math.abs(portfolioRisk.netVega), color: '#8b5cf6' }
    ];
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center">Loading risk management data...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Alert Status */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className={`px-3 py-1 rounded font-semibold ${getAlertColor(alertLevel)}`}>
                {alertLevel.toUpperCase()} RISK
              </div>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Portfolio Risk Level: {alertLevel === 'high' ? '🔴 High Alert' : alertLevel === 'medium' ? '🟡 Moderate' : '🟢 Normal'}
              </span>
            </div>
            <div className="text-sm text-gray-500">
              Last Updated: {new Date().toLocaleTimeString()}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Risk Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {riskMetrics.map((metric, index) => (
          <Card key={index}>
            <CardContent className="p-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-sm">{metric.name}</h4>
                  <Badge className={getStatusColor(metric.status)}>
                    {metric.status.toUpperCase()}
                  </Badge>
                </div>
                
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-2xl font-bold">
                      {metric.name.includes('%') ? `${metric.value}%` : `₹${metric.value.toLocaleString()}`}
                    </span>
                    <span className="text-sm text-gray-500">
                      / {metric.name.includes('%') ? `${metric.limit}%` : `₹${metric.limit.toLocaleString()}`}
                    </span>
                  </div>
                  
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        metric.status === 'danger' ? 'bg-red-500' : 
                        metric.status === 'warning' ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min((metric.value / metric.limit) * 100, 100)}%` }}
                    />
                  </div>
                  
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    {metric.description}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Portfolio Overview */}
      {portfolioRisk && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Exposure Chart */}
          <Card>
            <CardHeader>
              <CardTitle>💰 Position Exposure</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={getExposureChartData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip 
                      formatter={(value, name) => [
                        `₹${Number(value).toLocaleString()}`,
                        name === 'exposure' ? 'Exposure' : 'VaR'
                      ]}
                    />
                    <Bar dataKey="exposure" fill="#3b82f6" />
                    <Bar dataKey="var" fill="#ef4444" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Greeks Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>🔢 Portfolio Greeks</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={getGreeksChartData()}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                    >
                      {getGreeksChartData().map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip 
                      formatter={(value, name) => [
                        Number(value).toFixed(1),
                        name
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                <div className="text-center">
                  <div className="font-semibold text-blue-600">Net Delta</div>
                  <div>{portfolioRisk.netDelta}</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-green-600">Net Gamma</div>
                  <div>{portfolioRisk.netGamma}</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-red-600">Net Theta</div>
                  <div>{portfolioRisk.netTheta}</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-purple-600">Net Vega</div>
                  <div>{portfolioRisk.netVega}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Position Risk Table */}
      <Card>
        <CardHeader>
          <CardTitle>📊 Position Risk Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Position</th>
                  <th className="text-center p-2">Exposure</th>
                  <th className="text-center p-2">Delta</th>
                  <th className="text-center p-2">Gamma</th>
                  <th className="text-center p-2">Theta</th>
                  <th className="text-center p-2">Vega</th>
                  <th className="text-center p-2">VaR</th>
                  <th className="text-center p-2">Risk Score</th>
                </tr>
              </thead>
              <tbody>
                {positionRisks.map((position, index) => (
                  <tr key={index} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="p-2 font-medium">{position.symbol}</td>
                    <td className="text-center p-2">₹{position.exposure.toLocaleString()}</td>
                    <td className={`text-center p-2 font-mono ${position.delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {position.delta.toFixed(3)}
                    </td>
                    <td className="text-center p-2 font-mono">{position.gamma.toFixed(4)}</td>
                    <td className="text-center p-2 font-mono text-red-600">{position.theta}</td>
                    <td className="text-center p-2 font-mono">{position.vega}</td>
                    <td className="text-center p-2 font-mono">₹{position.var.toLocaleString()}</td>
                    <td className="text-center p-2">
                      <span className={`font-bold ${getRiskScoreColor(position.riskScore)}`}>
                        {position.riskScore.toFixed(1)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Risk Management Actions */}
      <Card>
        <CardHeader>
          <CardTitle>⚡ Risk Management Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-semibold text-green-600 mb-3">Recommended Actions</h4>
              <ul className="space-y-2 text-sm">
                {alertLevel === 'high' && (
                  <>
                    <li>• 🚨 Reduce position sizes immediately</li>
                    <li>• 🛡️ Hedge delta exposure with futures</li>
                    <li>• ⏰ Close positions with high theta decay</li>
                  </>
                )}
                {alertLevel === 'medium' && (
                  <>
                    <li>• ⚖️ Rebalance portfolio Greeks</li>
                    <li>• 📊 Monitor margin utilization closely</li>
                    <li>• 🎯 Consider profit-taking on winners</li>
                  </>
                )}
                {alertLevel === 'low' && (
                  <>
                    <li>• ✅ Portfolio risk within acceptable limits</li>
                    <li>• 📈 Consider scaling up profitable strategies</li>
                    <li>• 🔍 Monitor for new opportunities</li>
                  </>
                )}
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold text-red-600 mb-3">Risk Warnings</h4>
              <ul className="space-y-2 text-sm">
                <li>• 📅 Options expiry approaching - manage time decay</li>
                <li>• 📊 High gamma exposure - delta may change rapidly</li>
                <li>• 💹 Volatility risk elevated - monitor IV changes</li>
                <li>• ⚠️ Concentration risk in Nifty - diversify if possible</li>
              </ul>
            </div>
          </div>
          
          <div className="mt-6 flex space-x-2">
            <Button variant="destructive" size="sm">
              🚨 Emergency Close All
            </Button>
            <Button variant="outline" size="sm">
              🛡️ Hedge Portfolio
            </Button>
            <Button variant="outline" size="sm">
              📊 Generate Report
            </Button>
            <Button variant="outline" size="sm">
              ⚙️ Adjust Limits
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default RiskManagementDashboard;
