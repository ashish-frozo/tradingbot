"""
WebSocket Package
Real-time communication for trading updates
"""

from .socket_manager import SocketManager, get_socket_manager
from .events import setup_socket_events

__all__ = [
    "SocketManager",
    "get_socket_manager", 
    "setup_socket_events"
] 