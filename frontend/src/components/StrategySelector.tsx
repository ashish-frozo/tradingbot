import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { getApiUrl } from '../lib/config';

interface MarketData {
  spot: number;
  timestamp: string;
  volume: number;
}

interface OptionData {
  strike: number;
  call: {
    ltp: number;
    bid: number;
    ask: number;
    volume: number;
    oi: number;
    iv: number;
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
  };
  put: {
    ltp: number;
    bid: number;
    ask: number;
    volume: number;
    oi: number;
    iv: number;
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
  };
}

interface Signals {
  OR_width_pct: number;
  EM_pct: number;
  FB_ratio: number;
  RR25: number;
  rv_30m_volpts: number;
  pin_strike: number;
  pin_dist_pct: number;
  liquidity_ok: boolean;
  ORH: number;
  ORL: number;
  spot_open: number;
  current_spot: number;
}

interface StrategyScores {
  A: number; // Expiry Iron Fly
  B: number; // ORB + ITM Long
  C: number; // ATM Double-Calendar
  D: number; // Delta-Hedged Short Straddle
}

interface TradeLeg {
  type: 'BUY' | 'SELL';
  opt: 'CALL' | 'PUT';
  strike: number;
  dte: string;
  price?: number;
}

interface TradeRecommendation {
  strategy: string;
  legs: TradeLeg[];
  exits: {
    tp: string;
    sl: string;
    notes: string;
  };
  risk: {
    max_loss_R: number;
  };
}

export const StrategySelector: React.FC = () => {
  const [marketData, setMarketData] = useState<MarketData[]>([]);
  const [optionChain, setOptionChain] = useState<OptionData[]>([]);
  const [signals, setSignals] = useState<Signals | null>(null);
  const [scores, setScores] = useState<StrategyScores | null>(null);
  const [recommendation, setRecommendation] = useState<TradeRecommendation | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('NO-TRADE');
  const [isActive, setIsActive] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<string>('');

  const RISK_BUDGET = 10000; // ₹10,000 daily risk budget

  useEffect(() => {
    console.log('🔍 STRATEGY DEBUG: StrategySelector component mounted');
    const now = new Date();
    const currentTime = now.getHours() * 100 + now.getMinutes();
    
    console.log(`🔍 STRATEGY DEBUG: Current time: ${now.toTimeString()}, Time code: ${currentTime}`);
    
    // Active between 09:15 and 09:45
    if (currentTime >= 915 && currentTime <= 945) {
      console.log('✅ STRATEGY DEBUG: Within active window (09:15-09:45), starting data collection');
      setIsActive(true);
      startDataCollection();
    } else {
      console.log('❌ STRATEGY DEBUG: Outside active window (09:15-09:45), strategy selector inactive');
      setIsActive(false);
    }

    const interval = setInterval(() => {
      console.log('🔄 STRATEGY DEBUG: Interval tick - updating time and checking if active');
      updateTimeRemaining();
      if (isActive) {
        console.log('🔄 STRATEGY DEBUG: Strategy is active, fetching data and computing signals');
        fetchMarketData();
        computeSignals();
      }
    }, 60000); // Update every minute

    return () => clearInterval(interval);
  }, [isActive]);

  const updateTimeRemaining = () => {
    const now = new Date();
    const target = new Date();
    target.setHours(9, 45, 0, 0);
    
    if (now > target) {
      setTimeRemaining('Session Complete');
      return;
    }
    
    const diff = target.getTime() - now.getTime();
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    setTimeRemaining(`${minutes}:${seconds.toString().padStart(2, '0')}`);
  };

  const startDataCollection = async () => {
    console.log('🚀 STRATEGY DEBUG: Starting data collection');
    // Initialize with current market data
    await fetchMarketData();
    await fetchOptionChain();
    console.log('✅ STRATEGY DEBUG: Initial data collection completed');
  };

  const fetchMarketData = async () => {
    try {
      console.log('📊 STRATEGY DEBUG: Fetching market data (using mock data)');
      // Mock 1-minute market data - in real implementation, fetch from backend
      const mockData: MarketData = {
        spot: 25100 + (Math.random() - 0.5) * 100,
        timestamp: new Date().toISOString(),
        volume: Math.floor(Math.random() * 1000000) + 500000
      };
      
      console.log('📊 STRATEGY DEBUG: Mock market data generated:', mockData);
      setMarketData(prev => {
        const newData = [...prev.slice(-29), mockData];
        console.log(`📊 STRATEGY DEBUG: Market data array length: ${newData.length}`);
        return newData;
      });
    } catch (error) {
      console.error('❌ STRATEGY DEBUG: Error fetching market data:', error);
    }
  };

  const fetchOptionChain = async () => {
    try {
      const apiUrl = `${getApiUrl()}/api/option-chain`;
      console.log('🔗 STRATEGY DEBUG: Fetching option chain from:', apiUrl);
      
      const response = await fetch(apiUrl);
      console.log('🔗 STRATEGY DEBUG: Option chain response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('🔗 STRATEGY DEBUG: Option chain data received:', data);
        
        // Handle both new and legacy API response formats
        const chainData = data.option_chain || data.data || data;
        console.log('🔗 STRATEGY DEBUG: Processed option chain length:', chainData?.length || 0);
        
        setOptionChain(chainData || []);
      } else {
        console.error('❌ STRATEGY DEBUG: Failed to fetch option chain:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('❌ STRATEGY DEBUG: Error fetching option chain:', error);
    }
  };

  const computeSignals = () => {
    console.log('🧮 STRATEGY DEBUG: Computing signals...');
    console.log(`🧮 STRATEGY DEBUG: Market data length: ${marketData.length}, Option chain length: ${optionChain.length}`);
    
    if (marketData.length < 2 || optionChain.length === 0) {
      console.log('❌ STRATEGY DEBUG: Insufficient data for signal computation');
      return;
    }

    const currentSpot = marketData[marketData.length - 1].spot;
    console.log(`🧮 STRATEGY DEBUG: Current spot price: ${currentSpot}`);
    const spotOpen = marketData[0].spot;
    
    // 1. Opening Range (OR)
    const spots = marketData.map(d => d.spot);
    const ORH = Math.max(...spots);
    const ORL = Math.min(...spots);
    const OR_width_pct = ((ORH - ORL) / spotOpen) * 100;

    // 2. Expected Move (EM) from ATM straddle
    const atmStrike = findATMStrike(currentSpot);
    const atmCall = optionChain.find(opt => opt.strike === atmStrike)?.call;
    const atmPut = optionChain.find(opt => opt.strike === atmStrike)?.put;
    const EM_pct = atmCall && atmPut ? ((atmCall.ltp + atmPut.ltp) / currentSpot) * 100 : 0;

    // 3. Front/Back ATM IV ratio (mock next week data)
    const frontIV = atmCall?.iv || 0;
    const backIV = frontIV * 0.85; // Mock next week IV (typically lower)
    const FB_ratio = frontIV / backIV;

    // 4. 25Δ Risk Reversal
    const call25Delta = findStrikeByDelta(0.25, 'call');
    const put25Delta = findStrikeByDelta(0.25, 'put');
    const RR25 = (call25Delta?.iv || 0) - (put25Delta?.iv || 0);

    // 5. Realized Volatility (30min)
    const returns = [];
    for (let i = 1; i < marketData.length; i++) {
      returns.push(Math.log(marketData[i].spot / marketData[i-1].spot));
    }
    const rv_30m_volpts = returns.length > 0 ? 
      Math.sqrt(returns.reduce((sum, r) => sum + r*r, 0) / returns.length) * Math.sqrt(390) * 100 : 0;

    // 6. Pin risk
    const maxOIStrike = findMaxOIStrike();
    const pin_dist_pct = Math.abs(currentSpot - maxOIStrike) / currentSpot * 100;

    // 7. Liquidity check
    const atmSpread = atmCall && atmPut ? 
      (atmCall.ask - atmCall.bid + atmPut.ask - atmPut.bid) / 2 : 999;
    const liquidity_ok = atmSpread <= 2.0; // 2 tick threshold

    const newSignals: Signals = {
      OR_width_pct,
      EM_pct,
      FB_ratio,
      RR25,
      rv_30m_volpts,
      pin_strike: maxOIStrike,
      pin_dist_pct,
      liquidity_ok,
      ORH,
      ORL,
      spot_open: spotOpen,
      current_spot: currentSpot
    };

    console.log('📊 STRATEGY DEBUG: Computed signals:', newSignals);
    setSignals(newSignals);
    computeStrategyScores(newSignals);
  };

  const findATMStrike = (spot: number): number => {
    return optionChain.reduce((closest, opt) => 
      Math.abs(opt.strike - spot) < Math.abs(closest - spot) ? opt.strike : closest, 
      optionChain[0]?.strike || spot
    );
  };

  const findStrikeByDelta = (targetDelta: number, type: 'call' | 'put') => {
    const option = optionChain.find(opt => {
      const delta = type === 'call' ? opt.call.delta : Math.abs(opt.put.delta);
      return Math.abs(delta - targetDelta) < 0.05;
    });
    return option ? { ...option[type], strike: option.strike } : null;
  };

  const findMaxOIStrike = (): number => {
    return optionChain.reduce((maxStrike, opt) => {
      const totalOI = opt.call.oi + opt.put.oi;
      const maxOI = optionChain.find(o => o.strike === maxStrike);
      const maxTotalOI = maxOI ? maxOI.call.oi + maxOI.put.oi : 0;
      return totalOI > maxTotalOI ? opt.strike : maxStrike;
    }, optionChain[0]?.strike || 0);
  };

  const computeStrategyScores = (signals: Signals) => {
    console.log('🎯 STRATEGY DEBUG: Computing strategy scores for signals:', signals);
    const scores: StrategyScores = { A: 0, B: 0, C: 0, D: 0 };

    // A) Expiry Iron Fly
    if (signals.FB_ratio >= 1.15) scores.A += 1;
    if (signals.EM_pct <= 1.1 * signals.OR_width_pct) scores.A += 1;
    if (signals.pin_dist_pct <= 0.35 || signals.rv_30m_volpts < signals.FB_ratio * 10) scores.A += 1;
    if (Math.abs(signals.RR25) >= 2.0) scores.A -= 1;

    // B) ORB + ITM Long
    const breakout = checkBreakout(signals);
    if (breakout.hasBreakout) scores.B += 1;
    if (breakout.direction === 'up' && signals.RR25 > 0) scores.B += 1;
    if (breakout.direction === 'down' && signals.RR25 < 0) scores.B += 1;
    if (signals.FB_ratio <= 1.10) scores.B += 1;
    if (signals.EM_pct >= 1.3 * signals.OR_width_pct) scores.B += 1;

    // C) ATM Double-Calendar
    if (signals.FB_ratio >= 1.20) scores.C += 2;
    if (signals.pin_dist_pct <= 0.30 || signals.rv_30m_volpts < 15) scores.C += 1;
    if (signals.OR_width_pct >= 0.9) scores.C -= 1;

    // D) Delta-Hedged Short Straddle
    const ivRvDiff = (signals.FB_ratio * 15) - signals.rv_30m_volpts; // Mock IV in vol points
    if (ivRvDiff >= 3) scores.D += 2;
    if (signals.EM_pct <= 1.1 * signals.OR_width_pct) scores.D += 1;
    if (Math.abs(signals.RR25) >= 2.0) scores.D -= 1;

    console.log('📊 STRATEGY DEBUG: Final strategy scores:', scores);
    setScores(scores);
    selectBestStrategy(scores, signals);
  };

  const checkBreakout = (signals: Signals) => {
    const currentSpot = signals.current_spot;
    const avgVolume = marketData.slice(0, -5).reduce((sum, d) => sum + d.volume, 0) / Math.max(marketData.length - 5, 1);
    const recentVolume = marketData.slice(-5).reduce((sum, d) => sum + d.volume, 0) / 5;
    const volumeSurge = recentVolume >= 2 * avgVolume;

    if (currentSpot > signals.ORH * 1.0015 && volumeSurge) {
      return { hasBreakout: true, direction: 'up' as const };
    }
    if (currentSpot < signals.ORL * 0.9985 && volumeSurge) {
      return { hasBreakout: true, direction: 'down' as const };
    }
    return { hasBreakout: false, direction: null };
  };

  const selectBestStrategy = (scores: StrategyScores, signals: Signals) => {
    const maxScore = Math.max(scores.A, scores.B, scores.C, scores.D);
    console.log(`🏆 STRATEGY DEBUG: Best strategy selection - Max score: ${maxScore}, Liquidity OK: ${signals.liquidity_ok}`);
    
    if (maxScore < 2 || !signals.liquidity_ok) {
      console.log('❌ STRATEGY DEBUG: No trade - insufficient score or poor liquidity');
      setSelectedStrategy('NO-TRADE');
      setRecommendation(null);
      return;
    }

    let strategy = '';
    if (scores.A === maxScore) strategy = 'A';
    else if (scores.B === maxScore) strategy = 'B';
    else if (scores.C === maxScore) strategy = 'C';
    else if (scores.D === maxScore) strategy = 'D';

    console.log(`✅ STRATEGY DEBUG: Selected strategy: ${strategy} with score: ${maxScore}`);
    setSelectedStrategy(strategy);
    constructTrade(strategy, signals);
  };

  const constructTrade = (strategy: string, signals: Signals) => {
    console.log(`🔨 STRATEGY DEBUG: Constructing trade for strategy ${strategy}`);
    const atmStrike = findATMStrike(signals.current_spot);
    console.log(`🔨 STRATEGY DEBUG: ATM strike: ${atmStrike}, Current spot: ${signals.current_spot}`);
    
    switch (strategy) {
      case 'A': // Expiry Iron Fly
        const wingStrike1 = Math.round(atmStrike * 1.01);
        const wingStrike2 = Math.round(atmStrike * 0.99);
        const ironFlyRec = {
          strategy: 'Expiry Iron Fly',
          legs: [
            { type: 'SELL', opt: 'CALL', strike: atmStrike, dte: 'today' },
            { type: 'SELL', opt: 'PUT', strike: atmStrike, dte: 'today' },
            { type: 'BUY', opt: 'CALL', strike: wingStrike1, dte: 'today' },
            { type: 'BUY', opt: 'PUT', strike: wingStrike2, dte: 'today' }
          ],
          exits: {
            tp: '+35-50% of net credit',
            sl: 'spot trend >0.8% from entry OR -1.5x credit',
            notes: 'Entry: 09:25-09:50 on pullback'
          },
          risk: { max_loss_R: 0.5 }
        };
        console.log('📋 STRATEGY DEBUG: Iron Fly recommendation created:', ironFlyRec);
        setRecommendation(ironFlyRec);
        break;

      case 'B': // ORB + ITM Long
        const breakout = checkBreakout(signals);
        const itm70Strike = breakout.direction === 'up' ? 
          findStrikeByDelta(0.75, 'call') : findStrikeByDelta(0.75, 'put');
        setRecommendation({
          strategy: 'ORB + ITM Long',
          legs: [
            { 
              type: 'BUY', 
              opt: breakout.direction === 'up' ? 'CALL' : 'PUT', 
              strike: itm70Strike?.strike || atmStrike, 
              dte: 'today' 
            }
          ],
          exits: {
            tp: '+40-60% partial, trail with VWAP',
            sl: '-30% premium OR back inside OR',
            notes: 'Max 2 attempts per day'
          },
          risk: { max_loss_R: 0.3 }
        });
        break;

      case 'C': // ATM Double-Calendar
        setRecommendation({
          strategy: 'ATM Double-Calendar',
          legs: [
            { type: 'BUY', opt: 'CALL', strike: atmStrike, dte: 'next_week' },
            { type: 'BUY', opt: 'PUT', strike: atmStrike, dte: 'next_week' },
            { type: 'SELL', opt: 'CALL', strike: atmStrike, dte: 'today' },
            { type: 'SELL', opt: 'PUT', strike: atmStrike, dte: 'today' }
          ],
          exits: {
            tp: 'FB_ratio<=1.10 OR M2M>=+30%',
            sl: 'abs(spot-ATM)/spot >= 0.7%',
            notes: 'Skip if spreads>2 ticks'
          },
          risk: { max_loss_R: 0.5 }
        });
        break;

      case 'D': // Delta-Hedged Short Straddle
        setRecommendation({
          strategy: 'Delta-Hedged Short Straddle',
          legs: [
            { type: 'SELL', opt: 'CALL', strike: atmStrike, dte: 'today' },
            { type: 'SELL', opt: 'PUT', strike: atmStrike, dte: 'today' }
          ],
          exits: {
            tp: '+25-40% of credit',
            sl: 'Hard stop -1R including hedge slippage',
            notes: 'Delta-hedge on ±0.10 delta drift'
          },
          risk: { max_loss_R: 1.0 }
        });
        break;
    }
  };

  const getStrategyColor = (strategy: string) => {
    switch (strategy) {
      case 'A': return 'bg-blue-100 text-blue-800';
      case 'B': return 'bg-green-100 text-green-800';
      case 'C': return 'bg-purple-100 text-purple-800';
      case 'D': return 'bg-orange-100 text-orange-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Status Header */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Badge variant={isActive ? 'default' : 'secondary'}>
                {isActive ? '🟢 ACTIVE' : '🔴 INACTIVE'}
              </Badge>
              <span className="text-sm">
                Session: 09:15 - 09:45 | Time Remaining: {timeRemaining}
              </span>
            </div>
            <div className="text-sm text-gray-500">
              Risk Budget: ₹{RISK_BUDGET.toLocaleString()}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Signals Display */}
      {signals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-3">
              <div className="text-lg font-bold">{signals.OR_width_pct.toFixed(2)}%</div>
              <div className="text-xs text-gray-600">OR Width</div>
              <div className="text-xs">H: {signals.ORH.toFixed(0)} L: {signals.ORL.toFixed(0)}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-3">
              <div className="text-lg font-bold">{signals.EM_pct.toFixed(2)}%</div>
              <div className="text-xs text-gray-600">Expected Move</div>
              <div className="text-xs">ATM Straddle</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-3">
              <div className="text-lg font-bold">{signals.FB_ratio.toFixed(2)}</div>
              <div className="text-xs text-gray-600">FB Ratio</div>
              <div className="text-xs">Front/Back IV</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-3">
              <div className="text-lg font-bold">{signals.RR25.toFixed(1)}</div>
              <div className="text-xs text-gray-600">RR25 Skew</div>
              <div className="text-xs">Vol Points</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-3">
              <div className="text-lg font-bold">{signals.rv_30m_volpts.toFixed(1)}</div>
              <div className="text-xs text-gray-600">30m RV</div>
              <div className="text-xs">Vol Points</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-3">
              <div className="text-lg font-bold">{signals.pin_strike}</div>
              <div className="text-xs text-gray-600">Pin Strike</div>
              <div className="text-xs">{signals.pin_dist_pct.toFixed(2)}% away</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-3">
              <div className="text-lg font-bold">{signals.current_spot.toFixed(0)}</div>
              <div className="text-xs text-gray-600">Current Spot</div>
              <div className="text-xs">Open: {signals.spot_open.toFixed(0)}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-3">
              <Badge variant={signals.liquidity_ok ? 'default' : 'destructive'}>
                {signals.liquidity_ok ? '✅ LIQUID' : '❌ ILLIQUID'}
              </Badge>
              <div className="text-xs text-gray-600 mt-1">Market Condition</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Strategy Scores */}
      {scores && (
        <Card>
          <CardHeader>
            <CardTitle>Strategy Scores</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{scores.A}</div>
                <div className="text-sm">Iron Fly (A)</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{scores.B}</div>
                <div className="text-sm">ORB ITM (B)</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">{scores.C}</div>
                <div className="text-sm">Calendar (C)</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">{scores.D}</div>
                <div className="text-sm">Hedged Straddle (D)</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Final Recommendation */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Strategy Recommendation</span>
            <Badge className={getStrategyColor(selectedStrategy)}>
              {selectedStrategy === 'NO-TRADE' ? 'NO TRADE' : `Strategy ${selectedStrategy}`}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {recommendation ? (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg">{recommendation.strategy}</h3>
              
              <div>
                <h4 className="font-medium mb-2">Trade Legs:</h4>
                <div className="space-y-1">
                  {recommendation.legs.map((leg, idx) => (
                    <div key={idx} className="flex items-center space-x-2 text-sm">
                      <Badge variant={leg.type === 'BUY' ? 'default' : 'destructive'}>
                        {leg.type}
                      </Badge>
                      <span>{leg.opt} {leg.strike} ({leg.dte})</span>
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium text-green-600">Take Profit:</h4>
                  <p className="text-sm">{recommendation.exits.tp}</p>
                </div>
                <div>
                  <h4 className="font-medium text-red-600">Stop Loss:</h4>
                  <p className="text-sm">{recommendation.exits.sl}</p>
                </div>
              </div>
              
              <div>
                <h4 className="font-medium">Notes:</h4>
                <p className="text-sm text-gray-600">{recommendation.exits.notes}</p>
              </div>
              
              <div className="bg-yellow-50 p-3 rounded">
                <div className="font-medium">Risk: {recommendation.risk.max_loss_R}R</div>
                <div className="text-sm text-gray-600">
                  Max Loss: ₹{(RISK_BUDGET * recommendation.risk.max_loss_R).toLocaleString()}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              {selectedStrategy === 'NO-TRADE' ? 
                'No suitable strategy found. Conditions not met for any strategy.' :
                'Computing recommendation...'
              }
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default StrategySelector;
