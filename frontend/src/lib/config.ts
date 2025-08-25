/**
 * Smart API URL configuration
 * Uses relative URLs when on same domain (Railway production)
 * Uses localhost when in development
 */

export const getApiUrl = (): string => {
  // If we're on localhost, use the development backend
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    return 'http://localhost:8001';
  }
  
  // If we're on Railway or any other domain, use relative URLs
  // This assumes frontend and backend are served from the same domain
  return '';
};

export const getWsUrl = (): string => {
  // If we're on localhost, use the development WebSocket
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    return 'ws://localhost:8001';
  }
  
  // If we're on Railway or any other domain, use relative WebSocket URLs
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
};

// For backwards compatibility
export const API_BASE_URL = getApiUrl();
export const WS_BASE_URL = getWsUrl();
