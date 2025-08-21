import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { useAppStore } from '../stores/useAppStore';

interface AlertsPanelProps {
  className?: string;
}

export const AlertsPanel: React.FC<AlertsPanelProps> = ({ className = '' }) => {
  const { alerts, acknowledgeAlert, clearAlerts, addAlert } = useAppStore();
  const [integrationSettings, setIntegrationSettings] = useState({
    slack: { enabled: false, webhook: '' },
    telegram: { enabled: false, botToken: '', chatId: '' },
  });

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500';
      case 'high': return 'bg-orange-500';
      case 'medium': return 'bg-yellow-500';
      case 'low': return 'bg-blue-500';
      default: return 'bg-gray-500';
    }
  };

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'critical': return 'destructive' as const;
      case 'high': return 'destructive' as const;
      case 'medium': return 'secondary' as const;
      case 'low': return 'default' as const;
      default: return 'outline' as const;
    }
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'position_limit': return '📊';
      case 'daily_loss': return '💰';
      case 'circuit_breaker': return '🚨';
      case 'margin': return '⚠️';
      case 'system': return '🔧';
      default: return '🔔';
    }
  };

  const sendToSlack = async (message: string) => {
    if (!integrationSettings.slack.enabled || !integrationSettings.slack.webhook) {
      console.log('Slack not configured');
      return;
    }

    try {
      await fetch(integrationSettings.slack.webhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: `🤖 Trading Bot Alert: ${message}`,
          username: 'Trading Bot',
          icon_emoji: ':robot_face:'
        }),
      });
    } catch (error) {
      console.error('Failed to send Slack notification:', error);
    }
  };

  const sendToTelegram = async (message: string) => {
    if (!integrationSettings.telegram.enabled || !integrationSettings.telegram.botToken || !integrationSettings.telegram.chatId) {
      console.log('Telegram not configured');
      return;
    }

    try {
      await fetch(`https://api.telegram.org/bot${integrationSettings.telegram.botToken}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: integrationSettings.telegram.chatId,
          text: `🤖 Trading Bot Alert:\n${message}`,
          parse_mode: 'Markdown'
        }),
      });
    } catch (error) {
      console.error('Failed to send Telegram notification:', error);
    }
  };

  const handleAcknowledge = (alertId: string) => {
    acknowledgeAlert(alertId);
    const alert = alerts.find(a => a.id === alertId);
    if (alert) {
      sendToSlack(`Alert acknowledged: ${alert.message}`);
      sendToTelegram(`Alert acknowledged: ${alert.message}`);
    }
  };

  const testAlert = (type: 'slack' | 'telegram') => {
    const testMessage = `Test alert from Trading Bot Dashboard - ${new Date().toLocaleString()}`;
    
    if (type === 'slack') {
      sendToSlack(testMessage);
    } else {
      sendToTelegram(testMessage);
    }
    
    // Add a test alert to the panel
    addAlert({
      id: `test-${Date.now()}`,
      type: 'system',
      message: `Test ${type} integration sent`,
      severity: 'low',
      timestamp: new Date().toISOString(),
      acknowledged: false,
    });
  };

  // Generate some mock alerts if none exist
  const generateMockAlerts = () => {
    const mockAlerts = [
      {
        id: `alert-${Date.now()}-1`,
        type: 'position_limit' as const,
        message: 'Position limit reached: 48/50 slots used',
        severity: 'medium' as const,
        timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
        acknowledged: false,
      },
      {
        id: `alert-${Date.now()}-2`,
        type: 'daily_loss' as const,
        message: 'Daily loss approaching limit: -₹18,500 / -₹25,000',
        severity: 'high' as const,
        timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
        acknowledged: false,
      },
      {
        id: `alert-${Date.now()}-3`,
        type: 'margin' as const,
        message: 'High margin usage: 85% utilized',
        severity: 'medium' as const,
        timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        acknowledged: true,
      },
      {
        id: `alert-${Date.now()}-4`,
        type: 'system' as const,
        message: 'Strategy Vol-OI-Confirm restarted after error',
        severity: 'low' as const,
        timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
        acknowledged: true,
      },
    ];

    mockAlerts.forEach(alert => addAlert(alert));
  };

  const unacknowledgedAlerts = alerts.filter(a => !a.acknowledged);
  const acknowledgedAlerts = alerts.filter(a => a.acknowledged);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Alerts Panel Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>🔔 Alerts & Notifications</span>
            <div className="flex items-center space-x-2">
              <Badge variant={unacknowledgedAlerts.length > 0 ? 'destructive' : 'default'}>
                {unacknowledgedAlerts.length} Unread
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={generateMockAlerts}
                className="text-xs"
              >
                Generate Mock Alerts
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Real-time alerts and notifications for trading events
            </div>
            <div className="flex space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={clearAlerts}
                disabled={alerts.length === 0}
              >
                Clear All
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Integration Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Integration Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Slack Integration */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium flex items-center space-x-2">
                  <span>💬 Slack Integration</span>
                  <Badge variant={integrationSettings.slack.enabled ? 'default' : 'outline'}>
                    {integrationSettings.slack.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </h3>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIntegrationSettings(prev => ({
                    ...prev,
                    slack: { ...prev.slack, enabled: !prev.slack.enabled }
                  }))}
                >
                  {integrationSettings.slack.enabled ? 'Disable' : 'Enable'}
                </Button>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Webhook URL</label>
                <input
                  type="text"
                  placeholder="https://hooks.slack.com/services/..."
                  value={integrationSettings.slack.webhook}
                  onChange={(e) => setIntegrationSettings(prev => ({
                    ...prev,
                    slack: { ...prev.slack, webhook: e.target.value }
                  }))}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                />
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => testAlert('slack')}
                disabled={!integrationSettings.slack.enabled || !integrationSettings.slack.webhook}
                className="w-full"
              >
                Test Slack Integration
              </Button>
            </div>

            {/* Telegram Integration */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium flex items-center space-x-2">
                  <span>📱 Telegram Integration</span>
                  <Badge variant={integrationSettings.telegram.enabled ? 'default' : 'outline'}>
                    {integrationSettings.telegram.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </h3>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIntegrationSettings(prev => ({
                    ...prev,
                    telegram: { ...prev.telegram, enabled: !prev.telegram.enabled }
                  }))}
                >
                  {integrationSettings.telegram.enabled ? 'Disable' : 'Enable'}
                </Button>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Bot Token</label>
                <input
                  type="password"
                  placeholder="1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                  value={integrationSettings.telegram.botToken}
                  onChange={(e) => setIntegrationSettings(prev => ({
                    ...prev,
                    telegram: { ...prev.telegram, botToken: e.target.value }
                  }))}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Chat ID</label>
                <input
                  type="text"
                  placeholder="123456789"
                  value={integrationSettings.telegram.chatId}
                  onChange={(e) => setIntegrationSettings(prev => ({
                    ...prev,
                    telegram: { ...prev.telegram, chatId: e.target.value }
                  }))}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                />
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => testAlert('telegram')}
                disabled={!integrationSettings.telegram.enabled || !integrationSettings.telegram.botToken || !integrationSettings.telegram.chatId}
                className="w-full"
              >
                Test Telegram Integration
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Active Alerts */}
      {unacknowledgedAlerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-red-600 dark:text-red-400">
              🚨 Active Alerts ({unacknowledgedAlerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {unacknowledgedAlerts.map((alert) => (
                <div 
                  key={alert.id}
                  className="flex items-center justify-between p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800"
                >
                  <div className="flex items-center space-x-3">
                    <div className={`w-3 h-3 rounded-full ${getSeverityColor(alert.severity)}`} />
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-lg">{getAlertIcon(alert.type)}</span>
                        <span className="font-medium text-gray-900 dark:text-white">
                          {alert.message}
                        </span>
                        <Badge variant={getSeverityVariant(alert.severity)}>
                          {alert.severity.toUpperCase()}
                        </Badge>
                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        {new Date(alert.timestamp).toLocaleString()} • {alert.type.replace('_', ' ')}
                      </div>
                    </div>
                  </div>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAcknowledge(alert.id)}
                    className="text-green-600 border-green-600 hover:bg-green-50"
                  >
                    ✓ Acknowledge
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Alert History */}
      <Card>
        <CardHeader>
          <CardTitle>Alert History</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              No alerts yet. Click "Generate Mock Alerts" to see sample alerts.
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {alerts.slice().reverse().map((alert) => (
                <div 
                  key={alert.id}
                  className={`flex items-center justify-between p-3 rounded-lg border ${
                    alert.acknowledged 
                      ? 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700' 
                      : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <div className={`w-2 h-2 rounded-full ${getSeverityColor(alert.severity)}`} />
                    <div>
                      <div className="flex items-center space-x-2">
                        <span>{getAlertIcon(alert.type)}</span>
                        <span className={`text-sm ${alert.acknowledged ? 'text-gray-600 dark:text-gray-400' : 'text-gray-900 dark:text-white font-medium'}`}>
                          {alert.message}
                        </span>
                        <Badge variant={getSeverityVariant(alert.severity)} className="text-xs">
                          {alert.severity}
                        </Badge>
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-500">
                        {new Date(alert.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    {alert.acknowledged ? (
                      <Badge variant="outline" className="text-xs">
                        ✓ Acknowledged
                      </Badge>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleAcknowledge(alert.id)}
                        className="text-xs"
                      >
                        Acknowledge
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AlertsPanel; 