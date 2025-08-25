import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

interface KillSwitchStatus {
  data_fetching_allowed: boolean;
  reason: string;
  message: string;
  manual_override: boolean;
  emergency_stop: boolean;
  is_market_hours: boolean;
  current_time_ist: string;
  market_hours: string;
  is_weekday: boolean;
  market_status: string;
}

export const KillSwitchPanel: React.FC = () => {
  const [status, setStatus] = useState<KillSwitchStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8001'}/api/kill-switch/status`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
        setError(null);
      } else {
        setError('Failed to fetch kill switch status');
      }
    } catch (err) {
      setError('Network error: Unable to connect to server');
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action: 'activate' | 'deactivate' | 'emergency-stop' | 'emergency-restore') => {
    setActionLoading(action);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8001'}/api/kill-switch/${action}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        await fetchStatus(); // Refresh status
      } else {
        setError(`Failed to ${action} kill switch`);
      }
    } catch (err) {
      setError(`Network error during ${action}`);
    } finally {
      setActionLoading(null);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Kill Switch Control</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-sm text-gray-500">Loading kill switch status...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Kill Switch Control</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4">
            <div className="text-red-500 mb-2">{error}</div>
            <Button 
              onClick={fetchStatus} 
              size="sm"
              variant="outline"
            >
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const getStatusBadge = () => {
    if (!status) return null;

    if (status.emergency_stop) {
      return <Badge variant="destructive" className="bg-red-600">🚨 EMERGENCY STOP</Badge>;
    }
    
    if (status.manual_override) {
      return <Badge variant="destructive" className="bg-orange-500">🔴 MANUAL OFF</Badge>;
    }
    
    if (!status.is_market_hours) {
      return <Badge variant="secondary" className="bg-gray-500">🕐 MARKET CLOSED</Badge>;
    }
    
    if (!status.is_weekday) {
      return <Badge variant="secondary" className="bg-gray-500">📅 WEEKEND</Badge>;
    }
    
    return <Badge variant="default" className="bg-green-500">✅ ACTIVE</Badge>;
  };

  const getStatusColor = () => {
    if (!status) return 'border-gray-300';
    
    if (status.emergency_stop) return 'border-red-500 bg-red-50 dark:bg-red-900/10';
    if (status.manual_override) return 'border-orange-500 bg-orange-50 dark:bg-orange-900/10';
    if (!status.is_market_hours || !status.is_weekday) return 'border-gray-500 bg-gray-50 dark:bg-gray-900/10';
    return 'border-green-500 bg-green-50 dark:bg-green-900/10';
  };

  return (
    <Card className={`w-full ${getStatusColor()}`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            Kill Switch Control
            {getStatusBadge()}
          </CardTitle>
          <Button 
            onClick={fetchStatus} 
            size="sm" 
            variant="ghost"
            disabled={loading}
          >
            🔄
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status Information */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <strong>Current Time (IST):</strong>
            <div className="text-gray-600 dark:text-gray-300">
              {status?.current_time_ist}
            </div>
          </div>
          <div>
            <strong>Market Hours:</strong>
            <div className="text-gray-600 dark:text-gray-300">
              {status?.market_hours}
            </div>
          </div>
          <div>
            <strong>Data Fetching:</strong>
            <div className={!status?.data_fetching_allowed ? 'text-red-600' : 'text-green-600'}>
              {!status?.data_fetching_allowed ? '🚫 BLOCKED' : '✅ ALLOWED'}
            </div>
          </div>
          <div>
            <strong>Reason:</strong>
            <div className="text-gray-600 dark:text-gray-300 text-xs">
              {status?.reason}
            </div>
          </div>
        </div>

        {/* Manual Controls */}
        <div className="border-t pt-4">
          <h4 className="font-medium mb-3">Manual Controls</h4>
          <div className="grid grid-cols-2 gap-2">
            {/* Manual Override Controls */}
            <Button
              onClick={() => handleAction('activate')}
              disabled={actionLoading === 'activate' || status?.manual_override}
              variant="destructive"
              size="sm"
              className="w-full"
            >
              {actionLoading === 'activate' ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              ) : (
                '🔴 Manual Stop'
              )}
            </Button>

            <Button
              onClick={() => handleAction('deactivate')}
              disabled={actionLoading === 'deactivate' || !status?.manual_override}
              variant="default"
              size="sm"
              className="w-full bg-green-600 hover:bg-green-700"
            >
              {actionLoading === 'deactivate' ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              ) : (
                '🟢 Manual Start'
              )}
            </Button>

            {/* Emergency Controls */}
            <Button
              onClick={() => handleAction('emergency-stop')}
              disabled={actionLoading === 'emergency-stop' || status?.emergency_stop}
              variant="destructive"
              size="sm"
              className="w-full bg-red-700 hover:bg-red-800"
            >
              {actionLoading === 'emergency-stop' ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              ) : (
                '🚨 Emergency Stop'
              )}
            </Button>

            <Button
              onClick={() => handleAction('emergency-restore')}
              disabled={actionLoading === 'emergency-restore' || !status?.emergency_stop}
              variant="default"
              size="sm"
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              {actionLoading === 'emergency-restore' ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              ) : (
                '🔧 Emergency Restore'
              )}
            </Button>
          </div>
        </div>

        {/* Help Text */}
        <div className="text-xs text-gray-500 border-t pt-3">
          <p><strong>Manual Stop:</strong> Temporarily disable data fetching</p>
          <p><strong>Emergency Stop:</strong> Complete system halt for critical situations</p>
          <p><strong>Note:</strong> Market hours (9:15 AM - 3:30 PM IST) and weekdays are automatically enforced</p>
        </div>
      </CardContent>
    </Card>
  );
};
