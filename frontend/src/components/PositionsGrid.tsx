import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { usePositions, type Position } from '../stores/useAppStore';
import { formatCurrency, formatPercent, getPnlColor } from '../lib/utils';

interface PositionGridProps {
  showActions?: boolean;
}

interface PositionWithMetrics extends Position {
  timeRemaining?: number;
  stopLoss?: number;
  profitTarget?: number;
  breakevenPrice?: number;
}

export const PositionsGrid: React.FC<PositionGridProps> = ({
  showActions = true,
}) => {
  const positions = usePositions();

  // Enhanced positions with calculated metrics
  const enhancedPositions: PositionWithMetrics[] = React.useMemo(() => {
    return positions.map((position) => {
      const entryTime = new Date(position.entry_time).getTime();
      const now = Date.now();
      const timeElapsed = now - entryTime;
      const maxHoldTime = 10 * 60 * 1000; // 10 minutes max hold time
      const timeRemaining = Math.max(0, maxHoldTime - timeElapsed);

      // Calculate stop loss and profit target (example logic)
      const stopLossPercent = 0.25; // 25% stop loss
      const profitTargetPercent = 0.40; // 40% profit target
      
      const stopLoss = position.quantity > 0 
        ? position.avg_price * (1 - stopLossPercent)
        : position.avg_price * (1 + stopLossPercent);
        
      const profitTarget = position.quantity > 0
        ? position.avg_price * (1 + profitTargetPercent)
        : position.avg_price * (1 - profitTargetPercent);

      // Breakeven including estimated fees
      const estimatedFees = Math.abs(position.quantity) * position.avg_price * 0.001; // 0.1% fees
      const breakevenPrice = position.quantity > 0
        ? position.avg_price + (estimatedFees / Math.abs(position.quantity))
        : position.avg_price - (estimatedFees / Math.abs(position.quantity));

      return {
        ...position,
        timeRemaining,
        stopLoss,
        profitTarget,
        breakevenPrice,
      };
    });
  }, [positions]);

  const formatTimeRemaining = (milliseconds: number): string => {
    if (milliseconds <= 0) return '00:00';
    const minutes = Math.floor(milliseconds / 60000);
    const seconds = Math.floor((milliseconds % 60000) / 1000);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const getPositionStatus = (position: PositionWithMetrics): string => {
    if (position.timeRemaining === 0) return 'EXPIRED';
    if (position.current_price <= position.stopLoss!) return 'STOP_HIT';
    if (position.current_price >= position.profitTarget!) return 'TARGET_HIT';
    return 'ACTIVE';
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'ACTIVE': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'STOP_HIT': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'TARGET_HIT': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'EXPIRED': return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  const handleClosePosition = (symbol: string) => {
    // This would emit a close position request to the backend
    console.log(`Closing position for ${symbol}`);
  };

  const handleAdjustSL = (symbol: string) => {
    // This would open a dialog to adjust stop loss
    console.log(`Adjusting stop loss for ${symbol}`);
  };

  if (enhancedPositions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Active Positions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <div className="text-gray-500 dark:text-gray-400 mb-2">
              📈 No active positions
            </div>
            <div className="text-sm text-gray-400 dark:text-gray-500">
              Positions will appear here when trades are executed
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Active Positions ({enhancedPositions.length})</CardTitle>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Total P&L: <span className={getPnlColor(enhancedPositions.reduce((sum, p) => sum + p.unrealized_pnl, 0))}>
              {formatCurrency(enhancedPositions.reduce((sum, p) => sum + p.unrealized_pnl, 0))}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">Symbol</th>
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">Side/Qty</th>
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">Entry/LTP</th>
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">P&L</th>
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">Greeks</th>
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">SL/PT</th>
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">TTL</th>
                <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">Status</th>
                {showActions && (
                  <th className="text-left py-3 px-2 font-medium text-gray-900 dark:text-white">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
                             {enhancedPositions.map((position) => {
                 const status = getPositionStatus(position);
                
                return (
                  <tr key={position.symbol} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    {/* Symbol */}
                    <td className="py-4 px-2">
                      <div>
                        <div className="font-semibold text-gray-900 dark:text-white text-sm">
                          {position.symbol}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {position.strategy_id}
                        </div>
                      </div>
                    </td>

                    {/* Side/Quantity */}
                    <td className="py-4 px-2">
                      <div>
                        <Badge variant={position.quantity > 0 ? "default" : "destructive"} className="text-xs">
                          {position.quantity > 0 ? 'LONG' : 'SHORT'}
                        </Badge>
                        <div className="text-sm font-medium text-gray-900 dark:text-white mt-1">
                          {Math.abs(position.quantity)}
                        </div>
                      </div>
                    </td>

                    {/* Entry/LTP */}
                    <td className="py-4 px-2">
                      <div className="text-sm">
                        <div className="text-gray-600 dark:text-gray-400">
                          Entry: <span className="text-gray-900 dark:text-white font-medium">
                            {formatCurrency(position.avg_price)}
                          </span>
                        </div>
                        <div className="text-gray-600 dark:text-gray-400">
                          LTP: <span className="text-gray-900 dark:text-white font-medium">
                            {formatCurrency(position.current_price)}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          BE: {formatCurrency(position.breakevenPrice!)}
                        </div>
                      </div>
                    </td>

                    {/* P&L */}
                    <td className="py-4 px-2">
                      <div>
                        <div className={`font-bold text-sm ${getPnlColor(position.unrealized_pnl)}`}>
                          {formatCurrency(position.unrealized_pnl)}
                        </div>
                        <div className={`text-xs ${getPnlColor(position.unrealized_pnl)}`}>
                          {formatPercent((position.unrealized_pnl / (Math.abs(position.quantity) * position.avg_price)) * 100 / 100)}
                        </div>
                      </div>
                    </td>

                    {/* Greeks */}
                    <td className="py-4 px-2">
                      <div className="grid grid-cols-2 gap-1 text-xs">
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Δ:</span>
                          <span className="text-gray-900 dark:text-white ml-1">{(position.delta || 0).toFixed(2)}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Γ:</span>
                          <span className="text-gray-900 dark:text-white ml-1">{(position.gamma || 0).toFixed(3)}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Θ:</span>
                          <span className="text-gray-900 dark:text-white ml-1">{(position.theta || 0).toFixed(2)}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">ν:</span>
                          <span className="text-gray-900 dark:text-white ml-1">{(position.vega || 0).toFixed(2)}</span>
                        </div>
                      </div>
                    </td>

                    {/* SL/PT */}
                    <td className="py-4 px-2">
                      <div className="text-xs">
                        <div className="text-red-600 dark:text-red-400">
                          SL: {formatCurrency(position.stopLoss!)}
                        </div>
                        <div className="text-green-600 dark:text-green-400">
                          PT: {formatCurrency(position.profitTarget!)}
                        </div>
                      </div>
                    </td>

                    {/* TTL */}
                    <td className="py-4 px-2">
                      <div className="text-center">
                        <div className={`text-sm font-mono ${
                          position.timeRemaining! < 60000 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-white'
                        }`}>
                          {formatTimeRemaining(position.timeRemaining!)}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          remaining
                        </div>
                      </div>
                    </td>

                    {/* Status */}
                    <td className="py-4 px-2">
                      <Badge className={getStatusColor(status)}>
                        {status}
                      </Badge>
                    </td>

                    {/* Actions */}
                    {showActions && (
                      <td className="py-4 px-2">
                        <div className="flex space-x-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleAdjustSL(position.symbol)}
                            className="text-xs px-2 py-1"
                          >
                            SL
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleClosePosition(position.symbol)}
                            className="text-xs px-2 py-1"
                          >
                            Close
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}; 