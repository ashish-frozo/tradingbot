import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { useEquityCurve } from '../stores/useAppStore';
import { formatCurrency, formatPercent } from '../lib/utils';

interface EquityCurveProps {
  height?: number;
  showControls?: boolean;
}

interface EquityPoint {
  timestamp: string;
  value: number;
  formattedTime: string;
  pnl: number;
  pnlPercent: number;
}

export const EquityCurve: React.FC<EquityCurveProps> = ({
  height = 400,
  showControls = true,
}) => {
  const rawEquityData = useEquityCurve();

  // Transform the data for the chart
  const chartData: EquityPoint[] = React.useMemo(() => {
    if (!rawEquityData || rawEquityData.length === 0) {
      return [];
    }

    const startingValue = rawEquityData[0]?.value || 0;

    return rawEquityData.map((point) => {
      const date = new Date(point.timestamp);
      const pnl = point.value - startingValue;
      const pnlPercent = startingValue !== 0 ? (pnl / startingValue) * 100 : 0;

      return {
        timestamp: point.timestamp,
        value: point.value,
        formattedTime: date.toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
        pnl,
        pnlPercent,
      };
    });
  }, [rawEquityData]);

  // Calculate statistics
  const stats = React.useMemo(() => {
    if (chartData.length === 0) {
      return {
        currentValue: 0,
        totalPnl: 0,
        totalPnlPercent: 0,
        maxDrawdown: 0,
        maxDrawdownPercent: 0,
        highWaterMark: 0,
      };
    }

    const currentValue = chartData[chartData.length - 1].value;
    const startingValue = chartData[0].value;
    const totalPnl = currentValue - startingValue;
    const totalPnlPercent = startingValue !== 0 ? (totalPnl / startingValue) * 100 : 0;

    let maxDrawdown = 0;
    let maxDrawdownPercent = 0;
    let highWaterMark = startingValue;

    chartData.forEach((point) => {
      if (point.value > highWaterMark) {
        highWaterMark = point.value;
      }
      const drawdown = highWaterMark - point.value;
      const drawdownPercent = highWaterMark !== 0 ? (drawdown / highWaterMark) * 100 : 0;

      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
        maxDrawdownPercent = drawdownPercent;
      }
    });

    return {
      currentValue,
      totalPnl,
      totalPnlPercent,
      maxDrawdown,
      maxDrawdownPercent,
      highWaterMark,
    };
  }, [chartData]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload as EquityPoint;
      return (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
          <p className="text-sm font-medium text-gray-900 dark:text-white">
            {data.formattedTime}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Portfolio Value: <span className="font-semibold text-gray-900 dark:text-white">
              {formatCurrency(data.value)}
            </span>
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            P&L: <span className={`font-semibold ${data.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(data.pnl)} ({formatPercent(data.pnlPercent / 100)})
            </span>
          </p>
        </div>
      );
    }
    return null;
  };

  // Get line color based on performance
  const getLineColor = (pnl: number) => {
    if (pnl > 0) return '#10b981'; // green-500
    if (pnl < 0) return '#ef4444'; // red-500
    return '#6b7280'; // gray-500
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">Equity Curve</CardTitle>
          {showControls && (
            <div className="flex items-center space-x-4 text-sm">
              <div className="flex items-center space-x-2">
                <span className="text-gray-600 dark:text-gray-400">Total P&L:</span>
                <span className={`font-semibold ${stats.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(stats.totalPnl)}
                </span>
                <span className={`text-sm ${stats.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  ({formatPercent(stats.totalPnlPercent / 100)})
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-gray-600 dark:text-gray-400">Max DD:</span>
                <span className="text-red-600 font-semibold">
                  {formatCurrency(-stats.maxDrawdown)}
                </span>
                <span className="text-red-600 text-sm">
                  ({formatPercent(-stats.maxDrawdownPercent / 100)})
                </span>
              </div>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div style={{ height: `${height}px` }}>
          {chartData.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="text-gray-500 dark:text-gray-400 mb-2">
                  📈 No equity data available
                </div>
                <div className="text-sm text-gray-400 dark:text-gray-500">
                  Data will appear when trading begins
                </div>
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{
                  top: 5,
                  right: 30,
                  left: 20,
                  bottom: 5,
                }}
              >
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="formattedTime"
                  tick={{ fontSize: 12 }}
                  className="text-gray-600 dark:text-gray-400"
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  className="text-gray-600 dark:text-gray-400"
                  tickFormatter={(value) => formatCurrency(value)}
                />
                <Tooltip content={<CustomTooltip />} />
                
                {/* Reference line at starting value */}
                <ReferenceLine
                  y={chartData[0]?.value || 0}
                  stroke="#6b7280"
                  strokeDasharray="2 2"
                  strokeOpacity={0.5}
                />
                
                {/* Main equity line */}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={getLineColor(stats.totalPnl)}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{
                    r: 4,
                    fill: getLineColor(stats.totalPnl),
                  }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        
        {/* Performance summary */}
        {chartData.length > 0 && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="text-center">
              <div className="text-gray-600 dark:text-gray-400">Current Value</div>
              <div className="font-semibold text-gray-900 dark:text-white">
                {formatCurrency(stats.currentValue)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-600 dark:text-gray-400">High Water Mark</div>
              <div className="font-semibold text-gray-900 dark:text-white">
                {formatCurrency(stats.highWaterMark)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-600 dark:text-gray-400">Total Return</div>
              <div className={`font-semibold ${stats.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(stats.totalPnlPercent / 100)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-600 dark:text-gray-400">Max Drawdown</div>
              <div className="font-semibold text-red-600">
                {formatPercent(-stats.maxDrawdownPercent / 100)}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}; 