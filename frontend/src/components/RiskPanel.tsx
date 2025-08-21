import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { useAppStore } from '../stores/useAppStore';
import { formatCurrency, formatPercent, getPnlColor } from '../lib/utils';

interface RiskPanelProps {
  className?: string;
}

export const RiskPanel: React.FC<RiskPanelProps> = ({ className = '' }) => {
  const { riskMetrics } = useAppStore();

  // Calculate derived metrics
  const marginTotal = (riskMetrics?.margin_used || 0) + (riskMetrics?.margin_available || 0);
  const marginPercent = marginTotal > 0 ? (riskMetrics?.margin_used || 0) / marginTotal * 100 : 0;
  const dailyLossPercent = riskMetrics?.daily_loss_limit 
    ? Math.abs(riskMetrics.daily_pnl) / riskMetrics.daily_loss_limit * 100 
    : 0;
  const positionUtilization = riskMetrics?.max_position_limit 
    ? (riskMetrics.position_count / riskMetrics.max_position_limit) * 100 
    : 0;

  // Risk level indicators
  const getMarginRiskLevel = (percent: number) => {
    if (percent < 50) return { level: 'low', color: 'bg-green-500', text: 'Safe' };
    if (percent < 75) return { level: 'medium', color: 'bg-yellow-500', text: 'Moderate' };
    return { level: 'high', color: 'bg-red-500', text: 'High Risk' };
  };

  const getDailyLossRiskLevel = (percent: number) => {
    if (percent < 50) return { level: 'low', color: 'bg-green-500', text: 'Safe' };
    if (percent < 80) return { level: 'medium', color: 'bg-yellow-500', text: 'Warning' };
    return { level: 'high', color: 'bg-red-500', text: 'Critical' };
  };

  const getVixRiskLevel = (vix: number) => {
    if (vix < 15) return { level: 'low', color: 'bg-green-500', text: 'Low Vol' };
    if (vix < 25) return { level: 'medium', color: 'bg-yellow-500', text: 'Moderate Vol' };
    return { level: 'high', color: 'bg-red-500', text: 'High Vol' };
  };

  const marginRisk = getMarginRiskLevel(marginPercent);
  const dailyLossRisk = getDailyLossRiskLevel(dailyLossPercent);
  const vixRisk = getVixRiskLevel(riskMetrics?.vix_level || 0);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Risk Overview Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Risk Management Dashboard</span>
            <Badge 
              variant={riskMetrics?.circuit_breaker_status ? 'destructive' : 'default'}
              className="ml-2"
            >
              {riskMetrics?.circuit_breaker_status ? '🚨 Circuit Breaker ON' : '✅ Normal Trading'}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Margin Usage */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  Margin Usage
                </span>
                <Badge variant={marginRisk.level === 'high' ? 'destructive' : marginRisk.level === 'medium' ? 'secondary' : 'default'}>
                  {marginRisk.text}
                </Badge>
              </div>
              <Progress 
                value={marginPercent} 
                className="h-3"
                // @ts-ignore - Progress component styling
                style={{ '--progress-foreground': marginRisk.color }}
              />
              <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
                <span>{formatPercent(marginPercent)}</span>
                <span>{formatCurrency(riskMetrics?.margin_used || 0)} / {formatCurrency(marginTotal)}</span>
              </div>
            </div>

            {/* Daily Loss Tracking */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  Daily Loss Limit
                </span>
                <Badge variant={dailyLossRisk.level === 'high' ? 'destructive' : dailyLossRisk.level === 'medium' ? 'secondary' : 'default'}>
                  {dailyLossRisk.text}
                </Badge>
              </div>
              <Progress 
                value={dailyLossPercent} 
                className="h-3"
                // @ts-ignore - Progress component styling
                style={{ '--progress-foreground': dailyLossRisk.color }}
              />
              <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
                <span>{formatPercent(dailyLossPercent)}</span>
                <span className={getPnlColor(riskMetrics?.daily_pnl || 0)}>
                  {formatCurrency(riskMetrics?.daily_pnl || 0)} / {formatCurrency(-(riskMetrics?.daily_loss_limit || 25000))}
                </span>
              </div>
            </div>

            {/* Position Utilization */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  Position Slots
                </span>
                <Badge variant={positionUtilization > 80 ? 'destructive' : positionUtilization > 60 ? 'secondary' : 'default'}>
                  {positionUtilization > 80 ? 'High' : positionUtilization > 60 ? 'Medium' : 'Low'}
                </Badge>
              </div>
              <Progress 
                value={positionUtilization} 
                className="h-3"
              />
              <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
                <span>{formatPercent(positionUtilization)}</span>
                <span>{riskMetrics?.position_count || 0} / {riskMetrics?.max_position_limit || 50}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Risk Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Market Risk Indicators */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Market Risk Indicators</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">VIX Level</span>
              <div className="flex items-center space-x-2">
                <Badge variant={vixRisk.level === 'high' ? 'destructive' : vixRisk.level === 'medium' ? 'secondary' : 'default'}>
                  {vixRisk.text}
                </Badge>
                <span className="font-semibold">{(riskMetrics?.vix_level || 0).toFixed(2)}</span>
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">Current Drawdown</span>
              <span className={`font-semibold ${getPnlColor(-(riskMetrics?.current_drawdown || 0))}`}>
                {formatPercent(riskMetrics?.current_drawdown || 0)}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">Circuit Breaker</span>
              <Badge variant={riskMetrics?.circuit_breaker_status ? 'destructive' : 'default'}>
                {riskMetrics?.circuit_breaker_status ? 'ACTIVE' : 'INACTIVE'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* P&L Risk Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">P&L Risk Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">Total P&L</span>
              <span className={`font-semibold text-lg ${getPnlColor(riskMetrics?.total_pnl || 0)}`}>
                {formatCurrency(riskMetrics?.total_pnl || 0)}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">Daily P&L</span>
              <span className={`font-semibold ${getPnlColor(riskMetrics?.daily_pnl || 0)}`}>
                {formatCurrency(riskMetrics?.daily_pnl || 0)}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">Daily Loss Limit</span>
              <span className="font-semibold text-red-600 dark:text-red-400">
                {formatCurrency(-(riskMetrics?.daily_loss_limit || 25000))}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">Remaining Buffer</span>
              <span className={`font-semibold ${getPnlColor((riskMetrics?.daily_loss_limit || 25000) + (riskMetrics?.daily_pnl || 0))}`}>
                {formatCurrency((riskMetrics?.daily_loss_limit || 25000) + (riskMetrics?.daily_pnl || 0))}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Risk Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Risk Alerts & Warnings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {marginPercent > 75 && (
              <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <span className="text-red-500">⚠️</span>
                <span className="text-red-700 dark:text-red-300 font-medium">
                  High margin usage: {formatPercent(marginPercent)} - Consider reducing positions
                </span>
              </div>
            )}
            
            {dailyLossPercent > 80 && (
              <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <span className="text-red-500">🚨</span>
                <span className="text-red-700 dark:text-red-300 font-medium">
                  Approaching daily loss limit: {formatPercent(dailyLossPercent)} - Auto-flatten at 100%
                </span>
              </div>
            )}
            
            {(riskMetrics?.vix_level || 0) > 25 && (
              <div className="flex items-center space-x-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                <span className="text-yellow-500">⚡</span>
                <span className="text-yellow-700 dark:text-yellow-300 font-medium">
                  High volatility detected: VIX {(riskMetrics?.vix_level || 0).toFixed(2)} - Increased risk
                </span>
              </div>
            )}
            
            {positionUtilization > 80 && (
              <div className="flex items-center space-x-2 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800">
                <span className="text-orange-500">📊</span>
                <span className="text-orange-700 dark:text-orange-300 font-medium">
                  High position utilization: {formatPercent(positionUtilization)} - Limited capacity for new trades
                </span>
              </div>
            )}
            
            {marginPercent < 50 && dailyLossPercent < 30 && (riskMetrics?.vix_level || 0) < 20 && positionUtilization < 60 && (
              <div className="flex items-center space-x-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <span className="text-green-500">✅</span>
                <span className="text-green-700 dark:text-green-300 font-medium">
                  All risk metrics within safe parameters - Normal trading conditions
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default RiskPanel; 