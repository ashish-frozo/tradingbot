import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { useAppStore } from '../stores/useAppStore';

interface AdminPanelProps {
  className?: string;
}

export const AdminPanel: React.FC<AdminPanelProps> = ({ className = '' }) => {
  const { strategies, updateStrategy } = useAppStore();
  const [isConfirmingKillAll, setIsConfirmingKillAll] = useState(false);
  const [confirmingStrategy, setConfirmingStrategy] = useState<string | null>(null);

  const handleStrategyToggle = async (strategyId: string, newStatus: 'ACTIVE' | 'INACTIVE' | 'PAUSED') => {
    try {
      // In a real app, this would make an API call
      const strategy = strategies.find(s => s.strategy_id === strategyId);
      if (strategy) {
        updateStrategy({
          ...strategy,
          status: newStatus,
          last_updated: new Date().toISOString(),
        });
      }
      setConfirmingStrategy(null);
    } catch (error) {
      console.error('Error updating strategy:', error);
      alert('Failed to update strategy. Please try again.');
    }
  };

  const handleKillAllStrategies = async () => {
    if (!isConfirmingKillAll) {
      setIsConfirmingKillAll(true);
      setTimeout(() => setIsConfirmingKillAll(false), 5000); // Auto-cancel after 5 seconds
      return;
    }

    try {
      // Stop all strategies
      strategies.forEach(strategy => {
        if (strategy.status === 'ACTIVE') {
          updateStrategy({
            ...strategy,
            status: 'PAUSED',
            last_updated: new Date().toISOString(),
          });
        }
      });
      
      // Also trigger position kill switch
      const response = await fetch('http://localhost:8000/api/orders/kill-all', {
        method: 'POST',
      });
      
      if (!response.ok) throw new Error('Failed to kill all positions');
      
      alert('All strategies stopped and positions flattened!');
      setIsConfirmingKillAll(false);
    } catch (error) {
      console.error('Error in kill all:', error);
      alert('Error stopping strategies. Please try again.');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'bg-green-500';
      case 'PAUSED': return 'bg-yellow-500';
      case 'INACTIVE': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'default' as const;
      case 'PAUSED': return 'secondary' as const;
      case 'INACTIVE': return 'outline' as const;
      default: return 'outline' as const;
    }
  };

  // System controls
  const handleSystemRestart = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/admin/restart', {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to restart system');
      alert('System restart initiated!');
    } catch (error) {
      console.error('Error restarting system:', error);
      alert('Error restarting system. Please check manually.');
    }
  };

  const handleDataRefresh = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/admin/refresh-data', {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to refresh data');
      alert('Data refresh completed!');
    } catch (error) {
      console.error('Error refreshing data:', error);
      alert('Error refreshing data. Please try again.');
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Admin Panel Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>🔧 Admin Control Panel</span>
            <Badge variant="destructive" className="text-xs">
              ADMIN ACCESS
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            System administration and strategy management controls. Use with caution.
          </div>
        </CardContent>
      </Card>

      {/* Emergency Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="text-red-600 dark:text-red-400">
            🚨 Emergency Controls
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
              <div>
                <h3 className="font-medium text-red-800 dark:text-red-200">
                  Kill All Strategies & Positions
                </h3>
                <p className="text-sm text-red-600 dark:text-red-400">
                  Immediately stop all strategies and flatten all positions
                </p>
              </div>
              <Button
                variant="destructive"
                onClick={handleKillAllStrategies}
                className={`font-bold px-6 py-2 ${
                  isConfirmingKillAll ? 'bg-red-700 hover:bg-red-800' : 'bg-red-600 hover:bg-red-700'
                }`}
              >
                {isConfirmingKillAll ? '⚠️ CONFIRM KILL ALL' : '🚨 KILL ALL'}
              </Button>
            </div>
            
            {isConfirmingKillAll && (
              <div className="text-center text-sm text-red-600 dark:text-red-400">
                Click "CONFIRM KILL ALL" again within 5 seconds to proceed
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Strategy Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Strategy Management</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {strategies.map((strategy) => (
              <div 
                key={strategy.strategy_id}
                className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border"
              >
                <div className="flex items-center space-x-4">
                  <div className={`w-3 h-3 rounded-full ${getStatusColor(strategy.status)}`} />
                  <div>
                    <h3 className="font-medium text-gray-900 dark:text-white">
                      {strategy.name}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      ID: {strategy.strategy_id} | P&L: ₹{strategy.pnl.toLocaleString()} | 
                      Trades: {strategy.trades_count} | Win Rate: {strategy.win_rate.toFixed(1)}%
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-3">
                  <Badge variant={getStatusVariant(strategy.status)}>
                    {strategy.status}
                  </Badge>
                  
                  <div className="flex space-x-2">
                    {strategy.status !== 'ACTIVE' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (confirmingStrategy === `${strategy.strategy_id}-start`) {
                            handleStrategyToggle(strategy.strategy_id, 'ACTIVE');
                          } else {
                            setConfirmingStrategy(`${strategy.strategy_id}-start`);
                            setTimeout(() => setConfirmingStrategy(null), 3000);
                          }
                        }}
                        className="text-green-600 border-green-600 hover:bg-green-50"
                      >
                        {confirmingStrategy === `${strategy.strategy_id}-start` ? '✓ Confirm' : '▶️ Start'}
                      </Button>
                    )}
                    
                    {strategy.status === 'ACTIVE' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleStrategyToggle(strategy.strategy_id, 'PAUSED')}
                        className="text-yellow-600 border-yellow-600 hover:bg-yellow-50"
                      >
                        ⏸️ Pause
                      </Button>
                    )}
                    
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (confirmingStrategy === `${strategy.strategy_id}-stop`) {
                          handleStrategyToggle(strategy.strategy_id, 'INACTIVE');
                        } else {
                          setConfirmingStrategy(`${strategy.strategy_id}-stop`);
                          setTimeout(() => setConfirmingStrategy(null), 3000);
                        }
                      }}
                      className="text-red-600 border-red-600 hover:bg-red-50"
                    >
                      {confirmingStrategy === `${strategy.strategy_id}-stop` ? '✓ Confirm' : '⏹️ Stop'}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
            
            {strategies.length === 0 && (
              <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                No strategies loaded. Click "🎯 Strategies" to generate mock data.
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* System Controls */}
      <Card>
        <CardHeader>
          <CardTitle>System Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              <h3 className="font-medium text-gray-900 dark:text-white">Data Management</h3>
              <Button
                variant="outline"
                onClick={handleDataRefresh}
                className="w-full"
              >
                🔄 Refresh Market Data
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  // Clear all mock data
                  window.location.reload();
                }}
                className="w-full"
              >
                🗑️ Clear All Data
              </Button>
            </div>
            
            <div className="space-y-3">
              <h3 className="font-medium text-gray-900 dark:text-white">System Management</h3>
              <Button
                variant="outline"
                onClick={handleSystemRestart}
                className="w-full"
              >
                🔄 Restart Backend
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  // Export system logs
                  const logs = {
                    timestamp: new Date().toISOString(),
                    strategies: strategies,
                    system_status: 'exported'
                  };
                  const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `system-logs-${new Date().toISOString().split('T')[0]}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="w-full"
              >
                📥 Export Logs
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {strategies.filter(s => s.status === 'ACTIVE').length}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Active Strategies
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                {strategies.filter(s => s.status === 'PAUSED').length}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Paused Strategies
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">
                {strategies.filter(s => s.status === 'INACTIVE').length}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Inactive Strategies
              </div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {strategies.reduce((sum, s) => sum + s.trades_count, 0)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Total Trades
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminPanel; 