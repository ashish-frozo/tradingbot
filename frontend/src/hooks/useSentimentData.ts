import { useState, useEffect } from 'react';
import { getApiUrl } from '../lib/config';

interface SentimentData {
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
    ZG: number;
    NDT_z: number;
    VT: number;
    FB_ratio: number;
  };
}

interface ZScoreStats {
  [key: string]: {
    mean: number;
    std: number;
    count: number;
    last_updated: string;
  };
}

interface RegimePerformance {
  accuracy: number;
  avg_return: number;
  sharpe: number;
  count: number;
}

export const useSentimentData = () => {
  const [sentimentData, setSentimentData] = useState<SentimentData | null>(null);
  const [zscoreStats] = useState<ZScoreStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSentimentData = async () => {
    try {
      const response = await fetch(`${getApiUrl()}/api/sentiment`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const rawData = await response.json();
      
      // Transform API response to match component expectations
      const transformedData = {
        regime: rawData.regime,
        confidence: rawData.confidence,
        asof: rawData.timestamp,
        drivers: {
          DB: rawData.pillars?.directional_bias || 0,
          TP: rawData.pillars?.trend_propensity || 0,
          PR: rawData.pillars?.pinning_range || 0,
          RR25: rawData.metrics?.rr25 || 0,
          GEX_atm_z: rawData.metrics?.gex ? rawData.metrics.gex / 10000 : 0,
          pin_dist_pct: rawData.metrics?.max_oi_pin && rawData.metrics?.spot ? 
            Math.abs((rawData.metrics.spot - rawData.metrics.max_oi_pin) / rawData.metrics.spot * 100) : 0,
          ZG: rawData.metrics?.max_oi_pin || 0,
          NDT_z: 0, // Not available in current API
          VT: rawData.metrics?.vanna_tilt || 0,
          FB_ratio: 1.0 // Not available in current API
        }
      };
      
      setSentimentData(transformedData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch sentiment data');
      console.error('Error fetching sentiment data:', err);
    }
  };

  // Commented out to avoid 404 errors - endpoint not implemented
  // const fetchZScoreStats = async () => {
  //   try {
  //     const response = await fetch('http://localhost:8001/api/v1/sentiment/stats');
  //     if (!response.ok) {
  //       // Silently handle 404 for optional stats endpoint
  //       if (response.status === 404) {
  //         setZscoreStats(null);
  //         return;
  //       }
  //       throw new Error(`HTTP error! status: ${response.status}`);
  //     }
  //     const data = await response.json();
  //     setZscoreStats(data);
  //   } catch (err) {
  //     // Only log non-404 errors to avoid console spam
  //     if (err instanceof Error && !err.message.includes('404')) {
  //       console.error('Error fetching Z-score stats:', err);
  //     }
  //     setZscoreStats(null);
  //   }
  // };

  const getRegimePerformance = async (regime: string, days: number = 30): Promise<RegimePerformance | null> => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/sentiment/performance/${regime}?days=${days}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      console.error('Error fetching regime performance:', err);
      return null;
    }
  };

  const generateMockData = async (days: number = 60) => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/sentiment/generate-mock-data?days=${days}`, {
        method: 'POST'
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      console.error('Error generating mock data:', err);
      throw err;
    }
  };

  const runCalibration = async (lookbackDays: number = 60) => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/sentiment/calibrate?lookback_days=${lookbackDays}`, {
        method: 'POST'
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      console.error('Error running calibration:', err);
      throw err;
    }
  };

  const getCalibrationResult = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/v1/sentiment/calibration-result');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      console.error('Error fetching calibration result:', err);
      return null;
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchSentimentData();
      // Skip optional stats endpoint to avoid 404 errors
      // await fetchZScoreStats();
      setLoading(false);
    };

    loadData();

    // Set up polling for real-time updates during market hours
    const checkMarketHours = () => {
      const now = new Date();
      const hours = now.getHours();
      const minutes = now.getMinutes();
      const currentTime = hours * 60 + minutes;
      const startTime = 9 * 60 + 15; // 09:15 AM
      const endTime = 15 * 60 + 30;  // 03:30 PM
      
      // Check if it's a weekday (Monday=1, Sunday=0)
      const dayOfWeek = now.getDay();
      const isWeekday = dayOfWeek >= 1 && dayOfWeek <= 5;
      
      return isWeekday && currentTime >= startTime && currentTime <= endTime;
    };

    const interval = setInterval(() => {
      if (checkMarketHours()) {
        fetchSentimentData();
      }
    }, 60000); // Update every minute during market hours

    return () => clearInterval(interval);
  }, []);

  return {
    sentimentData,
    zscoreStats,
    loading,
    error,
    refetch: fetchSentimentData,
    getRegimePerformance,
    generateMockData,
    runCalibration,
    getCalibrationResult
  };
};
