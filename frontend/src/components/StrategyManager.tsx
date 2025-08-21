import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { formatCurrency, formatPercent, getPnlColor } from '../lib/utils';
import { motion } from 'framer-motion';

interface Strategy {
  strategy_id: string;
  name: string;
  description: string;
  status: 'ACTIVE' | 'PAUSED' | 'INACTIVE';
  pnl: number;
  trades_count: number;
  win_rate: number;
  max_drawdown: number;
  sharpe_ratio: number;
  profit_factor: number;
  last_updated: string;
  capital_allocated: number;
  risk_per_trade: number;
}

interface StrategyResponse {
  success: boolean;
  data: Strategy[];
  total_strategies: number;
  active_strategies: number;
}

export const StrategyManager: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    fetchStrategies();
    const interval = setInterval(fetchStrategies, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchStrategies = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/strategies');
      const data: StrategyResponse = await response.json();
      if (data.success) {
        setStrategies(data.data);
      }
      setLoading(false);
    } catch (error) {
      console.error('Error fetching strategies:', error);
      setLoading(false);
    }
  };

  const toggleStrategy = async (strategyId: string) => {
    setActionLoading(strategyId);
    try {
      const response = await fetch(`http://localhost:8001/api/strategies/${strategyId}/toggle`, {
        method: 'POST',
      });
      const result = await response.json();
      
      if (result.success) {
        // Update local state optimistically
        setStrategies(prev => prev.map(strategy => 
          strategy.strategy_id === strategyId 
            ? { ...strategy, status: strategy.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE' }
            : strategy
        ));
      }
    } catch (error) {
      console.error('Error toggling strategy:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const restartStrategy = async (strategyId: string) => {
    setActionLoading(strategyId);
    try {
      const response = await fetch(`http://localhost:8001/api/strategies/${strategyId}/restart`, {
        method: 'POST',
      });
      const result = await response.json();
      
      if (result.success) {
        // Refresh strategies after restart
        await fetchStrategies();
      }
    } catch (error) {
      console.error('Error restarting strategy:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'PAUSED':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'INACTIVE':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  const getPerformanceGrade = (strategy: Strategy): { grade: string; color: string } => {
    let score = 0;
    
    // Win rate scoring (30%)
    if (strategy.win_rate >= 70) score += 30;
    else if (strategy.win_rate >= 60) score += 25;
    else if (strategy.win_rate >= 50) score += 20;
    else if (strategy.win_rate >= 40) score += 15;
    
    // Sharpe ratio scoring (25%)
    if (strategy.sharpe_ratio >= 2) score += 25;
    else if (strategy.sharpe_ratio >= 1.5) score += 20;
    else if (strategy.sharpe_ratio >= 1) score += 15;
    else if (strategy.sharpe_ratio >= 0.5) score += 10;
    
    // Profit factor scoring (25%)
    if (strategy.profit_factor >= 2) score += 25;
    else if (strategy.profit_factor >= 1.5) score += 20;
    else if (strategy.profit_factor >= 1.2) score += 15;
    else if (strategy.profit_factor >= 1) score += 10;
    
    // Max drawdown scoring (20%)
    if (strategy.max_drawdown <= 5) score += 20;
    else if (strategy.max_drawdown <= 10) score += 15;
    else if (strategy.max_drawdown <= 15) score += 10;
    else if (strategy.max_drawdown <= 20) score += 5;
    
    if (score >= 80) return { grade: 'A', color: 'text-green-600' };
    if (score >= 70) return { grade: 'B', color: 'text-blue-600' };
    if (score >= 60) return { grade: 'C', color: 'text-yellow-600' };
    if (score >= 50) return { grade: 'D', color: 'text-orange-600' };
    return { grade: 'F', color: 'text-red-600' };
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Strategy Manager</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const totalPnl = strategies.reduce((sum, s) => sum + s.pnl, 0);
  const activeStrategies = strategies.filter(s => s.status === 'ACTIVE').length;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {strategies.length}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Total Strategies</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-green-600">
              {activeStrategies}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Active</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className={`text-2xl font-bold ${getPnlColor(totalPnl)}`}>
              {formatCurrency(totalPnl)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Total P&L</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {strategies.reduce((sum, s) => sum + s.trades_count, 0)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Total Trades</div>
          </CardContent>
        </Card>
      </div>

      {/* Strategy Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {strategies.map((strategy, index) => {
          const performanceGrade = getPerformanceGrade(strategy);
          
          return (
            <motion.div
              key={strategy.strategy_id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="relative h-full">
                <CardHeader className="pb-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg font-semibold">{strategy.name}</CardTitle>
                      <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        {strategy.description}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        ID: {strategy.strategy_id}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge className={getStatusColor(strategy.status)}>
                        {strategy.status}
                      </Badge>
                      <div className={`text-2xl font-bold ${performanceGrade.color}`}>
                        {performanceGrade.grade}
                      </div>
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent className="space-y-4">
                  {/* Key Metrics */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center">
                      <div className={`text-xl font-bold ${getPnlColor(strategy.pnl)}`}>
                        {formatCurrency(strategy.pnl)}
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">P&L</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-xl font-bold text-gray-900 dark:text-white">
                        {strategy.win_rate.toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">Win Rate</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-xl font-bold text-gray-900 dark:text-white">
                        {strategy.trades_count}
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">Trades</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-xl font-bold text-red-600">
                        {strategy.max_drawdown.toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">Max DD</div>
                    </div>
                  </div>

                  {/* Performance Details */}
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Sharpe Ratio:</span>
                      <span className="font-medium">{strategy.sharpe_ratio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Profit Factor:</span>
                      <span className="font-medium">{strategy.profit_factor.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Capital:</span>
                      <span className="font-medium">{formatCurrency(strategy.capital_allocated)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Risk/Trade:</span>
                      <span className="font-medium">{formatPercent(strategy.risk_per_trade)}</span>
                    </div>
                  </div>

                  {/* Controls */}
                  <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                    <div className="flex space-x-2">
                      <Button
                        variant={strategy.status === 'ACTIVE' ? 'destructive' : 'default'}
                        size="sm"
                        onClick={() => toggleStrategy(strategy.strategy_id)}
                        disabled={actionLoading === strategy.strategy_id}
                        className="flex-1"
                      >
                        {actionLoading === strategy.strategy_id ? (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        ) : (
                          strategy.status === 'ACTIVE' ? 'Pause' : 'Start'
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => restartStrategy(strategy.strategy_id)}
                        disabled={actionLoading === strategy.strategy_id}
                        className="flex-1"
                      >
                        {actionLoading === strategy.strategy_id ? (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                        ) : (
                          'Restart'
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Last Updated */}
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Last updated: {new Date(strategy.last_updated).toLocaleString('en-IN')}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {strategies.length === 0 && (
        <Card>
          <CardContent className="text-center py-12">
            <div className="text-gray-500 dark:text-gray-400 mb-2">
              🎯 No strategies configured
            </div>
            <div className="text-sm text-gray-400 dark:text-gray-500">
              Strategy management will appear here when strategies are deployed
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
