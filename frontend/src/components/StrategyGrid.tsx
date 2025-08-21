import React from 'react';
import { StrategyCard } from './StrategyCard';
import { useAppStore } from '../stores/useAppStore';

export const StrategyGrid: React.FC = () => {
  const { strategies } = useAppStore();

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
        Active Strategies
      </h2>
      
      {!strategies || strategies.length === 0 ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No active strategies
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {strategies.map((strategy, index) => (
            <StrategyCard key={strategy.name} strategy={strategy} />
          ))}
        </div>
      )}
    </div>
  );
};
