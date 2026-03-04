"""Database package for PS_RCS_PROJECT.

Exports the main repository class as ReceiptRepository for backward compatibility,
and also exposes ReceiptDatabase directly.
"""

from .core import init_db, get_session
from .models import Base, ReceiptScan
from .repository import ReceiptDatabase

# Alias ReceiptDatabase as ReceiptRepository for existing imports
ReceiptRepository = ReceiptDatabase

__all__ = [
    'init_db',
    'get_session',
    'Base',
    'ReceiptScan',
    'ReceiptDatabase',
    'ReceiptRepository',
]