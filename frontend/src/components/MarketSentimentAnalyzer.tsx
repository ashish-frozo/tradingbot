import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { useSentimentData } from '../hooks/useSentimentData';

interface OptionData {
  strike: number;
  call: {
    ltp: number;
    bid: number;
    ask: number;
    volume: number;
    oi: number;
    oi_change: number;
    iv: number;
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    vanna: number;
    charm: number;
  };
  put: {
    ltp: number;
    bid: number;
    ask: number;
    volume: number;
    oi: number;
    oi_change: number;
    iv: number;
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    vanna: number;
    charm: number;
  };
}

/*
interface MarketData {
  spot: number;
  timestamp: string;
  volume: number;
}

interface SentimentResult {
  regime: 'Bullish' | 'Bearish' | 'Sideways' | 'Balanced';
  confidence: number;
  asof: string;
  drivers: {
    DB: number;
    TP: number;
    PR: number;
    RR25: number;
    GEX_atm_z: number;
    pin_dist_pct: number;
    IV_rank: number;
    NDT_z: number;
    VT: number;
    FB_ratio: number;
  };
}

interface HistoricalStats {
  ndt_mean: number;
  ndt_std: number;
  gex_mean: number;
  gex_std: number;
  charm_mean: number;
  charm_std: number;
}
*/

const MarketSentimentAnalyzer: React.FC = () => {
  const { sentimentData, loading, error } = useSentimentData();
  const [isActive, setIsActive] = useState(false);

  // Check if market is in active window (09:15-09:45)
  const checkActiveWindow = () => {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const currentTime = hours * 60 + minutes;
    const startTime = 9 * 60 + 15; // 09:15
    const endTime = 9 * 60 + 45;   // 09:45
    return currentTime >= startTime && currentTime <= endTime;
  };

  useEffect(() => {
    const active = checkActiveWindow();
    setIsActive(active);
  }, []);

  const getRegimeColor = (regime: string) => {
    switch (regime) {
      case 'Bullish': return 'bg-green-500';
      case 'Bearish': return 'bg-red-500';
      case 'Sideways': return 'bg-yellow-500';
      default: return 'bg-gray-500';
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.7) return 'text-green-600';
    if (confidence >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>🧠 Market Sentiment Analysis</span>
            <div className="flex items-center gap-2">
              <Badge variant={isActive ? 'default' : 'secondary'}>
                {isActive ? '🟢 Active (09:15-09:45)' : '🔴 Inactive'}
              </Badge>
              {sentimentData && (
                <Badge className={getRegimeColor(sentimentData.regime)}>
                  {sentimentData.regime}
                </Badge>
              )}
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {sentimentData ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Main Result */}
              <Card className="col-span-full">
                <CardContent className="pt-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold mb-2">{sentimentData.regime}</div>
                    <div className={`text-xl ${getConfidenceColor(sentimentData.confidence)}`}>
                      Confidence: {(sentimentData.confidence * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-gray-500 mt-2">
                      As of: {new Date(sentimentData.asof).toLocaleTimeString()}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Pillar Scores */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">📊 Pillar Scores</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span>Directional Bias (DB):</span>
                      <Badge variant={sentimentData.drivers.DB > 0 ? 'default' : sentimentData.drivers.DB < 0 ? 'destructive' : 'secondary'}>
                        {sentimentData.drivers.DB > 0 ? '+' : ''}{sentimentData.drivers.DB}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span>Trend Propensity (TP):</span>
                      <Badge variant={sentimentData.drivers.TP >= 2 ? 'destructive' : sentimentData.drivers.TP === 1 ? 'default' : 'secondary'}>
                        {sentimentData.drivers.TP}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span>Pinning/Range (PR):</span>
                      <Badge variant={sentimentData.drivers.PR >= 2 ? 'default' : 'secondary'}>
                        {sentimentData.drivers.PR}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Key Metrics */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">📈 Key Metrics</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>RR25:</span>
                      <span className={sentimentData.drivers.RR25 > 1 ? 'text-green-600' : sentimentData.drivers.RR25 < -1 ? 'text-red-600' : ''}>
                        {sentimentData.drivers.RR25.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>GEX Z-Score:</span>
                      <span className={sentimentData.drivers.GEX_atm_z < -1 ? 'text-red-600' : sentimentData.drivers.GEX_atm_z > 1 ? 'text-green-600' : ''}>
                        {sentimentData.drivers.GEX_atm_z.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Pin Distance:</span>
                      <span className={sentimentData.drivers.pin_dist_pct <= 0.3 ? 'text-yellow-600' : ''}>
                        {sentimentData.drivers.pin_dist_pct.toFixed(2)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Zero Gamma:</span>
                      <span>{sentimentData.drivers.ZG.toFixed(0)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Advanced Metrics */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">🔬 Advanced Metrics</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>NDT Z-Score:</span>
                      <span className={sentimentData.drivers.NDT_z > 0.5 ? 'text-green-600' : sentimentData.drivers.NDT_z < -0.5 ? 'text-red-600' : ''}>
                        {sentimentData.drivers.NDT_z.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Vanna Tilt:</span>
                      <span className={sentimentData.drivers.VT > 0 ? 'text-green-600' : sentimentData.drivers.VT < 0 ? 'text-red-600' : ''}>
                        {sentimentData.drivers.VT.toFixed(0)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>FB Ratio:</span>
                      <span className={sentimentData.drivers.FB_ratio >= 1.15 ? 'text-yellow-600' : ''}>
                        {sentimentData.drivers.FB_ratio.toFixed(3)}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : loading ? (
            <div className="text-center py-8">
              <div className="text-gray-500">
                Computing sentiment analysis...
              </div>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <div className="text-red-500">
                Error: {error}
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <div className="text-gray-500">
                {isActive ? 'Computing sentiment analysis...' : 'Sentiment analysis active during 09:15-09:45 IST'}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Interpretation Guide */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">📚 Interpretation Guide</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <h4 className="font-semibold mb-2">Regime Meanings:</h4>
              <ul className="space-y-1">
                <li><span className="text-green-600">●</span> <strong>Bullish:</strong> Trend up likely, DB≥1, TP≥1, PR≤1, spot&gt;ZG</li>
                <li><span className="text-red-600">●</span> <strong>Bearish:</strong> Trend down likely, DB≤-1, TP≥1, PR≤1, spot&lt;ZG</li>
                <li><span className="text-yellow-600">●</span> <strong>Sideways:</strong> Range/pin likely, PR≥2 or low conviction</li>
                <li><span className="text-gray-600">●</span> <strong>Balanced:</strong> Mixed signals, reduce size</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-2">Key Concepts:</h4>
              <ul className="space-y-1">
                <li><strong>GEX:</strong> Dealer gamma exposure - negative = trend prone</li>
                <li><strong>RR25:</strong> 25Δ risk reversal - skew direction</li>
                <li><strong>NDT:</strong> Net delta tilt from option flow</li>
                <li><strong>Vanna:</strong> Delta sensitivity to IV changes</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MarketSentimentAnalyzer;
