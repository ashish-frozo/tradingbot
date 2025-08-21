import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { formatCurrency, getPnlColor } from '../utils/formatters';

interface Strategy {
  name: string;
  status: string;
  pnl: number;
  dayPnl: number;
  positions: number;
}

interface StrategyCardProps {
  strategy?: Strategy;
  showControls?: boolean;
}

export const StrategyCard: React.FC<StrategyCardProps> = ({ strategy, showControls = true }) => {
  if (!strategy) {
    return (
      <Card className="p-6">
        <div className="text-center text-gray-500">
          No strategy data available
        </div>
      </Card>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active': return 'bg-green-500';
      case 'paused': return 'bg-yellow-500';
      case 'inactive': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">{strategy.name}</CardTitle>
          <Badge className={`${getStatusColor(strategy.status)} text-white`}>
            {strategy.status.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* P&L Section */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-600">Total P&L</p>
            <p className={`text-lg font-semibold ${getPnlColor(strategy.pnl)}`}>
              {formatCurrency(strategy.pnl)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Day P&L</p>
            <p className={`text-lg font-semibold ${getPnlColor(strategy.dayPnl)}`}>
              {formatCurrency(strategy.dayPnl)}
            </p>
          </div>
        </div>

        {/* Positions */}
        <div>
          <p className="text-sm text-gray-600">Active Positions</p>
          <p className="text-lg font-semibold">{strategy.positions}</p>
        </div>

        {/* Mock metrics for display */}
        <div className="border-t pt-3 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Win Rate:</span>
            <span className="font-medium">71.1%</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Total Trades:</span>
            <span className="font-medium">45</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Profit Factor:</span>
            <span className="font-medium">1.8</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
