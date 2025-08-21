/**
 * Custom hooks for fetching and managing API data
 */

import { useState, useEffect } from 'react';
import { apiService } from '../services/api';

// Hook for equity data
export const useEquityData = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiService.getEquityData();
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch equity data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    
    // Set up polling every 30 seconds
    const interval = setInterval(fetchData, 30000);
    
    return () => clearInterval(interval);
  }, []);

  return { data, loading, error };
};

// Hook for positions data
export const usePositions = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async (isInitial = false) => {
      try {
        if (isInitial) {
          setLoading(true);
        }
        setError(null);
        const response = await apiService.getPositions();
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch positions');
      } finally {
        if (isInitial) {
          setLoading(false);
        }
      }
    };

    // Initial fetch with loading indicator
    fetchData(true);
    
    // Set up polling every 10 seconds for positions (without loading indicator)
    const interval = setInterval(() => fetchData(false), 10000);
    
    return () => clearInterval(interval);
  }, []);

  return { data, loading, error };
};

// Hook for risk metrics
export const useRiskMetrics = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async (isInitial = false) => {
      try {
        if (isInitial) {
          setLoading(true);
        }
        setError(null);
        const response = await apiService.getRiskMetrics();
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch risk metrics');
      } finally {
        if (isInitial) {
          setLoading(false);
        }
      }
    };

    // Initial fetch with loading indicator
    fetchData(true);
    
    // Set up polling every 15 seconds for risk metrics (without loading indicator)
    const interval = setInterval(() => fetchData(false), 15000);
    
    return () => clearInterval(interval);
  }, []);

  return { data, loading, error };
};

// Hook for market data
export const useMarketData = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async (isInitial = false) => {
      try {
        if (isInitial) {
          setLoading(true);
        }
        setError(null);
        const response = await apiService.getMarketData();
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch market data');
      } finally {
        if (isInitial) {
          setLoading(false);
        }
      }
    };

    // Initial fetch with loading indicator
    fetchData(true);
    
    // Set up polling every 5 seconds for market data (without loading indicator)
    const interval = setInterval(() => fetchData(false), 5000);
    
    return () => clearInterval(interval);
  }, []);

  return { data, loading, error };
};
