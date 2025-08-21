import React from 'react';
import { usePositions } from '../hooks/useApiData';

interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price?: number;
  ltp?: number;
  pnl: number;
  pnl_percent: number;
}

export const PositionsTable: React.FC = () => {
  const { data: positionsData, loading, error } = usePositions();
  const positions = positionsData?.positions || [];

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Positions</h2>
        <div className="flex items-center justify-center h-32">
          <div className="text-gray-500">Loading positions...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Positions</h2>
        <div className="flex items-center justify-center h-32">
          <div className="text-red-500">Error loading positions: {error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Current Positions</h2>
      
      {!positions || positions.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No open positions
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full table-auto">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Symbol</th>
                <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Qty</th>
                <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">Avg Price</th>
                <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">LTP</th>
                <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">P&L</th>
                <th className="px-4 py-2 text-right text-sm font-medium text-gray-700">P&L %</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position: Position, index: number) => (
                <tr key={index} className="border-t border-gray-200 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {position.symbol}
                  </td>
                  <td className={`px-4 py-3 text-sm text-right font-medium ${
                    position.quantity > 0 ? 'text-blue-600' : 'text-orange-600'
                  }`}>
                    {position.quantity > 0 ? '+' : ''}{position.quantity}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-700">
                    ₹{(position.avg_price || 0).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-700">
                    ₹{(position.ltp || position.current_price || 0).toFixed(2)}
                  </td>
                  <td className={`px-4 py-3 text-sm text-right font-medium ${
                    (position.pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {(position.pnl || 0) >= 0 ? '+' : ''}₹{(position.pnl || 0).toFixed(2)}
                  </td>
                  <td className={`px-4 py-3 text-sm text-right font-medium ${
                    (position.pnl_percent || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {(position.pnl_percent || 0) >= 0 ? '+' : ''}{(position.pnl_percent || 0).toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {/* Summary Row */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-gray-700">
                Total P&L:
              </span>
              <span className={`text-sm font-bold ${
                positions.reduce((sum: number, pos: Position) => sum + pos.pnl, 0) >= 0 
                  ? 'text-green-600' 
                  : 'text-red-600'
              }`}>
                {positions.reduce((sum: number, pos: Position) => sum + pos.pnl, 0) >= 0 ? '+' : ''}
                ₹{positions.reduce((sum: number, pos: Position) => sum + pos.pnl, 0).toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
