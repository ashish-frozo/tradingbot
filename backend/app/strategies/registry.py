"""
Strategy Registry and Dynamic Loading System
Manages registration, loading, and lifecycle of trading strategies.

This system provides the pluggable architecture for strategies, allowing
dynamic loading, configuration management, and runtime control.
"""

import asyncio
import importlib
import inspect
from typing import Dict, Type, Optional, List, Any, Callable
from pathlib import Path
from datetime import datetime
import traceback

from app.core.logging import get_logger
from app.strategies.base import BaseStrategy
from app.db.models.strategy import Strategy as StrategyModel, StrategyStatus


logger = get_logger(__name__)


class StrategyRegistry:
    """
    Central registry for managing trading strategies.
    
    Provides registration, loading, configuration, and lifecycle management
    for all strategies in the system.
    """
    
    def __init__(self):
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._instances: Dict[str, BaseStrategy] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._strategy_metadata: Dict[str, Dict[str, Any]] = {}
        self._loaded_modules: Dict[str, Any] = {}
        
        logger.info("Strategy registry initialized")
    
    def register_strategy(
        self,
        strategy_class: Type[BaseStrategy],
        name: Optional[str] = None,
        description: str = "",
        version: str = "1.0",
        author: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a strategy class in the registry.
        
        Args:
            strategy_class: Strategy class to register
            name: Strategy name (defaults to class name)
            description: Strategy description
            version: Strategy version
            author: Strategy author
            metadata: Additional metadata
        """
        strategy_name = name or strategy_class.__name__
        
        try:
            if not issubclass(strategy_class, BaseStrategy):
                raise ValueError(f"Strategy class must inherit from BaseStrategy")
            
            if strategy_name in self._strategies:
                logger.warning(f"Strategy {strategy_name} already registered, overwriting")
            
            self._strategies[strategy_name] = strategy_class
            self._strategy_metadata[strategy_name] = {
                'class_name': strategy_class.__name__,
                'module': strategy_class.__module__,
                'description': description,
                'version': version,
                'author': author,
                'registered_at': datetime.utcnow().isoformat(),
                'metadata': metadata or {}
            }
            
            logger.info(f"Strategy registered: {strategy_name} v{version}")
            
        except Exception as e:
            logger.error(f"Error registering strategy {strategy_name}: {e}")
            raise
    
    def unregister_strategy(self, strategy_name: str) -> bool:
        """
        Unregister a strategy from the registry.
        
        Args:
            strategy_name: Name of strategy to unregister
            
        Returns:
            bool: True if unregistered successfully
        """
        try:
            if strategy_name not in self._strategies:
                logger.warning(f"Strategy {strategy_name} not found in registry")
                return False
            
            # Stop instance if running
            if strategy_name in self._instances:
                asyncio.create_task(self.stop_strategy(strategy_name))
            
            # Remove from registry
            del self._strategies[strategy_name]
            del self._strategy_metadata[strategy_name]
            
            if strategy_name in self._configs:
                del self._configs[strategy_name]
            
            logger.info(f"Strategy unregistered: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering strategy {strategy_name}: {e}")
            return False
    
    def load_strategies_from_directory(self, directory: Path) -> int:
        """
        Dynamically load strategies from a directory.
        
        Args:
            directory: Directory containing strategy modules
            
        Returns:
            int: Number of strategies loaded
        """
        loaded_count = 0
        
        try:
            if not directory.exists():
                logger.warning(f"Strategy directory not found: {directory}")
                return 0
            
            # Find all Python files in directory and subdirectories
            strategy_files = list(directory.rglob("*.py"))
            
            for file_path in strategy_files:
                if file_path.name.startswith("__"):
                    continue
                
                try:
                    # Convert file path to module path
                    relative_path = file_path.relative_to(directory.parent)
                    module_path = str(relative_path.with_suffix("")).replace("/", ".")
                    
                    # Load module
                    module = importlib.import_module(module_path)
                    self._loaded_modules[module_path] = module
                    
                    # Find strategy classes in module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BaseStrategy) and 
                            obj != BaseStrategy and 
                            not inspect.isabstract(obj)):
                            
                            # Auto-register strategy
                            strategy_name = getattr(obj, 'STRATEGY_NAME', name)
                            description = getattr(obj, 'DESCRIPTION', obj.__doc__ or "")
                            version = getattr(obj, 'VERSION', "1.0")
                            author = getattr(obj, 'AUTHOR', "")
                            
                            self.register_strategy(
                                obj, 
                                strategy_name, 
                                description, 
                                version, 
                                author
                            )
                            loaded_count += 1
                            
                except Exception as e:
                    logger.error(f"Error loading strategy from {file_path}: {e}")
                    continue
            
            logger.info(f"Loaded {loaded_count} strategies from {directory}")
            return loaded_count
            
        except Exception as e:
            logger.error(f"Error loading strategies from directory {directory}: {e}")
            return 0
    
    def reload_strategy(self, strategy_name: str) -> bool:
        """
        Reload a strategy from its module.
        
        Args:
            strategy_name: Name of strategy to reload
            
        Returns:
            bool: True if reloaded successfully
        """
        try:
            if strategy_name not in self._strategies:
                logger.error(f"Strategy {strategy_name} not found in registry")
                return False
            
            # Get module path
            strategy_class = self._strategies[strategy_name]
            module_path = strategy_class.__module__
            
            if module_path not in self._loaded_modules:
                logger.error(f"Module {module_path} not found in loaded modules")
                return False
            
            # Stop existing instance
            if strategy_name in self._instances:
                asyncio.create_task(self.stop_strategy(strategy_name))
            
            # Reload module
            module = importlib.reload(self._loaded_modules[module_path])
            self._loaded_modules[module_path] = module
            
            # Re-register strategy class
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseStrategy) and 
                    obj != BaseStrategy and 
                    not inspect.isabstract(obj) and
                    getattr(obj, 'STRATEGY_NAME', name) == strategy_name):
                    
                    old_metadata = self._strategy_metadata.get(strategy_name, {})
                    self.register_strategy(
                        obj, 
                        strategy_name,
                        old_metadata.get('description', ''),
                        old_metadata.get('version', '1.0'),
                        old_metadata.get('author', '')
                    )
                    break
            
            logger.info(f"Strategy reloaded: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error reloading strategy {strategy_name}: {e}")
            return False
    
    async def create_strategy_instance(
        self,
        strategy_name: str,
        config: Dict[str, Any],
        db_session=None,
        redis_client=None,
        broker_client=None,
        risk_manager=None,
        order_manager=None
    ) -> Optional[BaseStrategy]:
        """
        Create an instance of a registered strategy.
        
        Args:
            strategy_name: Name of strategy to instantiate
            config: Strategy configuration
            db_session: Database session
            redis_client: Redis client
            broker_client: Broker client
            risk_manager: Risk manager
            order_manager: Order manager
            
        Returns:
            Optional[BaseStrategy]: Strategy instance if created successfully
        """
        try:
            if strategy_name not in self._strategies:
                logger.error(f"Strategy {strategy_name} not registered")
                return None
            
            # Get strategy class
            strategy_class = self._strategies[strategy_name]
            
            # Create instance
            instance = strategy_class(
                strategy_name=strategy_name,
                config=config,
                db_session=db_session,
                redis_client=redis_client,
                broker_client=broker_client,
                risk_manager=risk_manager,
                order_manager=order_manager
            )
            
            # Store configuration
            self._configs[strategy_name] = config.copy()
            
            logger.info(f"Strategy instance created: {strategy_name}")
            return instance
            
        except Exception as e:
            logger.error(f"Error creating strategy instance {strategy_name}: {e}")
            logger.error(traceback.format_exc())
            return None
    
    async def start_strategy(
        self,
        strategy_name: str,
        config: Dict[str, Any],
        db_session=None,
        redis_client=None,
        broker_client=None,
        risk_manager=None,
        order_manager=None
    ) -> bool:
        """
        Start a strategy instance.
        
        Args:
            strategy_name: Name of strategy to start
            config: Strategy configuration
            db_session: Database session
            redis_client: Redis client
            broker_client: Broker client
            risk_manager: Risk manager
            order_manager: Order manager
            
        Returns:
            bool: True if started successfully
        """
        try:
            # Stop existing instance if running
            if strategy_name in self._instances:
                await self.stop_strategy(strategy_name)
            
            # Create new instance
            instance = await self.create_strategy_instance(
                strategy_name,
                config,
                db_session,
                redis_client,
                broker_client,
                risk_manager,
                order_manager
            )
            
            if not instance:
                return False
            
            # Start strategy
            if await instance.start():
                self._instances[strategy_name] = instance
                logger.info(f"Strategy started: {strategy_name}")
                return True
            else:
                logger.error(f"Failed to start strategy: {strategy_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting strategy {strategy_name}: {e}")
            return False
    
    async def stop_strategy(self, strategy_name: str) -> bool:
        """
        Stop a running strategy instance.
        
        Args:
            strategy_name: Name of strategy to stop
            
        Returns:
            bool: True if stopped successfully
        """
        try:
            if strategy_name not in self._instances:
                logger.warning(f"Strategy {strategy_name} is not running")
                return True
            
            instance = self._instances[strategy_name]
            
            # Stop strategy
            if await instance.stop():
                del self._instances[strategy_name]
                logger.info(f"Strategy stopped: {strategy_name}")
                return True
            else:
                logger.error(f"Failed to stop strategy: {strategy_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping strategy {strategy_name}: {e}")
            return False
    
    async def pause_strategy(self, strategy_name: str) -> bool:
        """
        Pause a running strategy.
        
        Args:
            strategy_name: Name of strategy to pause
            
        Returns:
            bool: True if paused successfully
        """
        try:
            if strategy_name not in self._instances:
                logger.error(f"Strategy {strategy_name} is not running")
                return False
            
            instance = self._instances[strategy_name]
            return await instance.pause()
            
        except Exception as e:
            logger.error(f"Error pausing strategy {strategy_name}: {e}")
            return False
    
    async def resume_strategy(self, strategy_name: str) -> bool:
        """
        Resume a paused strategy.
        
        Args:
            strategy_name: Name of strategy to resume
            
        Returns:
            bool: True if resumed successfully
        """
        try:
            if strategy_name not in self._instances:
                logger.error(f"Strategy {strategy_name} is not running")
                return False
            
            instance = self._instances[strategy_name]
            return await instance.resume()
            
        except Exception as e:
            logger.error(f"Error resuming strategy {strategy_name}: {e}")
            return False
    
    def get_strategy_instance(self, strategy_name: str) -> Optional[BaseStrategy]:
        """
        Get running strategy instance.
        
        Args:
            strategy_name: Name of strategy
            
        Returns:
            Optional[BaseStrategy]: Strategy instance if running
        """
        return self._instances.get(strategy_name)
    
    def list_registered_strategies(self) -> List[Dict[str, Any]]:
        """
        List all registered strategies.
        
        Returns:
            List[Dict[str, Any]]: List of strategy information
        """
        strategies = []
        
        for name, metadata in self._strategy_metadata.items():
            strategy_info = {
                'name': name,
                'is_running': name in self._instances,
                'status': None,
                **metadata
            }
            
            # Add runtime status if running
            if name in self._instances:
                instance = self._instances[name]
                strategy_info['status'] = 'active' if instance.state.is_active else 'inactive'
                strategy_info['is_trading'] = instance.state.is_trading
                strategy_info['performance'] = instance.get_performance_summary()
                strategy_info['health'] = instance.get_health_status()
            
            strategies.append(strategy_info)
        
        return strategies
    
    def list_running_strategies(self) -> List[str]:
        """
        List names of currently running strategies.
        
        Returns:
            List[str]: List of running strategy names
        """
        return list(self._instances.keys())
    
    def get_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        Get strategy configuration.
        
        Args:
            strategy_name: Name of strategy
            
        Returns:
            Optional[Dict[str, Any]]: Strategy configuration if exists
        """
        return self._configs.get(strategy_name)
    
    def update_strategy_config(self, strategy_name: str, config: Dict[str, Any]) -> bool:
        """
        Update strategy configuration.
        
        Args:
            strategy_name: Name of strategy
            config: New configuration
            
        Returns:
            bool: True if updated successfully
        """
        try:
            if strategy_name not in self._strategies:
                logger.error(f"Strategy {strategy_name} not registered")
                return False
            
            self._configs[strategy_name] = config.copy()
            
            # Update running instance config if exists
            if strategy_name in self._instances:
                instance = self._instances[strategy_name]
                instance.config.update(config)
                logger.info(f"Updated config for running strategy: {strategy_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating strategy config {strategy_name}: {e}")
            return False
    
    async def stop_all_strategies(self) -> Dict[str, bool]:
        """
        Stop all running strategies.
        
        Returns:
            Dict[str, bool]: Results of stop operations
        """
        results = {}
        
        for strategy_name in list(self._instances.keys()):
            results[strategy_name] = await self.stop_strategy(strategy_name)
        
        return results
    
    def get_registry_status(self) -> Dict[str, Any]:
        """
        Get overall registry status.
        
        Returns:
            Dict[str, Any]: Registry status information
        """
        return {
            'total_registered': len(self._strategies),
            'total_running': len(self._instances),
            'registered_strategies': list(self._strategies.keys()),
            'running_strategies': list(self._instances.keys()),
            'loaded_modules': list(self._loaded_modules.keys())
        }


# Global registry instance
strategy_registry = StrategyRegistry()


def register_strategy(
    name: Optional[str] = None,
    description: str = "",
    version: str = "1.0",
    author: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> Callable:
    """
    Decorator for registering strategy classes.
    
    Args:
        name: Strategy name
        description: Strategy description
        version: Strategy version
        author: Strategy author
        metadata: Additional metadata
        
    Returns:
        Callable: Decorator function
    """
    def decorator(strategy_class: Type[BaseStrategy]) -> Type[BaseStrategy]:
        strategy_registry.register_strategy(
            strategy_class, name, description, version, author, metadata
        )
        return strategy_class
    
    return decorator 