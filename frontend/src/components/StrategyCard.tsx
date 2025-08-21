import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { useStrategies, type Strategy } from '../stores/useAppStore';
import { formatCurrency, formatPercent, getPnlColor } from '../lib/utils';

interface StrategyCardProps {
  strategy?: Strategy;
  showControls?: boolean;
}

interface StrategyMetrics {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  riskRewardRatio: number;
  profitFactor: number;
  maxDrawdown: number;
  maxDrawdownPercent: number;
  calmarRatio: number;
  sharpeRatio: number;
  totalPnl: number;
  dailyPnl: number;
  monthlyReturn: number;
}

export const StrategyCard: React.FC<StrategyCardProps> = ({
  strategy,
  showControls = true,
}) => {
  // Calculate enhanced metrics
  const metrics: StrategyMetrics = React.useMemo(() => {
    if (!strategy) {
      return {
        totalTrades: 0,
        winningTrades: 0,
        losingTrades: 0,
        winRate: 0,
        avgWin: 0,
        avgLoss: 0,
        riskRewardRatio: 0,
        profitFactor: 0,
        maxDrawdown: 0,
        maxDrawdownPercent: 0,
        calmarRatio: 0,
        sharpeRatio: 0,
        totalPnl: 0,
        dailyPnl: 0,
        monthlyReturn: 0,
      };
    }

    const totalTrades = strategy.trades_count;
    const winningTrades = Math.floor(totalTrades * (strategy.win_rate / 100));
    const losingTrades = totalTrades - winningTrades;
    
    // Estimated average win/loss (simplified calculation)
    const avgWin = strategy.pnl > 0 ? strategy.pnl / Math.max(winningTrades, 1) : 0;
    const avgLoss = strategy.pnl < 0 ? Math.abs(strategy.pnl) / Math.max(losingTrades, 1) : 1000;
    
    const riskRewardRatio = avgLoss > 0 ? avgWin / avgLoss : 0;
    const profitFactor = strategy.profit_factor || (avgWin * winningTrades) / Math.max(avgLoss * losingTrades, 1);
    
    const maxDrawdownPercent = strategy.max_drawdown;
    const maxDrawdown = Math.abs(strategy.pnl * (maxDrawdownPercent / 100));
    
    // Calmar Ratio = Annual Return / Max Drawdown
    const annualReturn = strategy.pnl * 252; // Assuming daily returns
    const calmarRatio = maxDrawdownPercent > 0 ? (annualReturn / 100000) / maxDrawdownPercent : 0;
    
    const monthlyReturn = strategy.pnl * 30; // Simplified monthly return

    return {
      totalTrades,
      winningTrades,
      losingTrades,
      winRate: strategy.win_rate,
      avgWin,
      avgLoss,
      riskRewardRatio,
      profitFactor,
      maxDrawdown,
      maxDrawdownPercent,
      calmarRatio,
      sharpeRatio: strategy.sharpe_ratio,
      totalPnl: strategy.pnl,
      dailyPnl: strategy.pnl, // Simplified
      monthlyReturn,
    };
  }, [strategy]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'INACTIVE':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
      case 'PAUSED':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  const getPerformanceGrade = (metrics: StrategyMetrics): { grade: string; color: string } => {
    let score = 0;
    
    // Win rate scoring (30%)
    if (metrics.winRate >= 70) score += 30;
    else if (metrics.winRate >= 60) score += 25;
    else if (metrics.winRate >= 50) score += 20;
    else if (metrics.winRate >= 40) score += 15;
    
    // Risk-Reward ratio scoring (25%)
    if (metrics.riskRewardRatio >= 2) score += 25;
    else if (metrics.riskRewardRatio >= 1.5) score += 20;
    else if (metrics.riskRewardRatio >= 1) score += 15;
    else if (metrics.riskRewardRatio >= 0.5) score += 10;
    
    // Profit factor scoring (25%)
    if (metrics.profitFactor >= 2) score += 25;
    else if (metrics.profitFactor >= 1.5) score += 20;
    else if (metrics.profitFactor >= 1.2) score += 15;
    else if (metrics.profitFactor >= 1) score += 10;
    
    // Max drawdown scoring (20%)
    if (metrics.maxDrawdownPercent <= 5) score += 20;
    else if (metrics.maxDrawdownPercent <= 10) score += 15;
    else if (metrics.maxDrawdownPercent <= 15) score += 10;
    else if (metrics.maxDrawdownPercent <= 20) score += 5;
    
    if (score >= 80) return { grade: 'A', color: 'text-green-600' };
    if (score >= 70) return { grade: 'B', color: 'text-blue-600' };
    if (score >= 60) return { grade: 'C', color: 'text-yellow-600' };
    if (score >= 50) return { grade: 'D', color: 'text-orange-600' };
    return { grade: 'F', color: 'text-red-600' };
  };

  const handleToggleStrategy = () => {
    if (!strategy) return;
    const newStatus = strategy.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE';
    console.log(`Toggling strategy ${strategy.strategy_id} to ${newStatus}`);
  };

  const handleRestartStrategy = () => {
    if (!strategy) return;
    console.log(`Restarting strategy ${strategy.strategy_id}`);
  };

  if (!strategy) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center text-gray-500 dark:text-gray-400">
            No strategy data available
          </div>
        </CardContent>
      </Card>
    );
  }

  const performanceGrade = getPerformanceGrade(metrics);

  return (
    <Card className="relative">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg font-semibold">{strategy.name}</CardTitle>
            <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
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
      
      <CardContent className="space-y-6">
        {/* Key Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {metrics.winRate.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Win Rate</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {metrics.riskRewardRatio.toFixed(2)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">R:R Ratio</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {metrics.profitFactor.toFixed(2)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Profit Factor</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">
              {metrics.maxDrawdownPercent.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Max DD</div>
          </div>
        </div>

        {/* Performance Details */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Total Trades:</span>
              <span className="font-medium text-gray-900 dark:text-white">{metrics.totalTrades}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Winning Trades:</span>
              <span className="font-medium text-green-600">{metrics.winningTrades}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Losing Trades:</span>
              <span className="font-medium text-red-600">{metrics.losingTrades}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Avg Win:</span>
              <span className="font-medium text-green-600">{formatCurrency(metrics.avgWin)}</span>
            </div>
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Total P&L:</span>
              <span className={`font-medium ${getPnlColor(metrics.totalPnl)}`}>
                {formatCurrency(metrics.totalPnl)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Avg Loss:</span>
              <span className="font-medium text-red-600">{formatCurrency(-metrics.avgLoss)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Sharpe Ratio:</span>
              <span className="font-medium text-gray-900 dark:text-white">{metrics.sharpeRatio.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Calmar Ratio:</span>
              <span className="font-medium text-gray-900 dark:text-white">{metrics.calmarRatio.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* Monthly Performance */}
        <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
          <div className="text-sm font-medium text-gray-900 dark:text-white mb-2">
            Estimated Monthly Performance
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-600 dark:text-gray-400">Projected Return:</span>
            <span className={`font-bold ${getPnlColor(metrics.monthlyReturn)}`}>
              {formatCurrency(metrics.monthlyReturn)}
            </span>
          </div>
        </div>

        {/* Controls */}
        {showControls && (
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <div className="flex space-x-2">
              <Button
                variant={strategy.status === 'ACTIVE' ? 'destructive' : 'default'}
                size="sm"
                onClick={handleToggleStrategy}
                className="flex-1"
              >
                {strategy.status === 'ACTIVE' ? 'Pause' : 'Start'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRestartStrategy}
                className="flex-1"
              >
                Restart
              </Button>
            </div>
          </div>
        )}

        {/* Last Updated */}
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Last updated: {new Date(strategy.last_updated).toLocaleString('en-IN')}
        </div>
      </CardContent>
    </Card>
  );
};

export const StrategyGrid: React.FC = () => {
  const strategies = useStrategies();

  if (strategies.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Strategy Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <div className="text-gray-500 dark:text-gray-400 mb-2">
              🎯 No strategies configured
            </div>
            <div className="text-sm text-gray-400 dark:text-gray-500">
              Strategy performance will appear here when strategies are active
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          Strategy Performance ({strategies.length})
        </h2>
        <div className="text-sm text-gray-600 dark:text-gray-400">
          Total P&L: <span className={getPnlColor(strategies.reduce((sum, s) => sum + s.pnl, 0))}>
            {formatCurrency(strategies.reduce((sum, s) => sum + s.pnl, 0))}
          </span>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {strategies.map((strategy) => (
          <StrategyCard key={strategy.strategy_id} strategy={strategy} />
        ))}
      </div>
    </div>
  );
}; 