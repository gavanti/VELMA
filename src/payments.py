"""
Módulo de pagos para Chakana Platform.

Este módulo maneja todo el procesamiento de pagos y canjes de Aurios.
"""

from datetime import datetime
from typing import Optional, Dict, List

AURIO_VALUE_USD = 0.01  # Constraint: El Aurio vale exactamente $0.01
MINIMUM_REDEEM_AMOUNT = 1000  # Mínimo de Aurios para canjear


class PaymentProcessor:
    """Procesador de pagos y canjes de Aurios."""
    
    def __init__(self, db_connection):
        """
        Inicializa el procesador de pagos.
        
        Args:
            db_connection: Conexión a la base de datos
        """
        self.db = db_connection
    
    def calculate_aurio_value(self, aurios: int) -> float:
        """
        Calcula el valor en USD de una cantidad de Aurios.
        
        Args:
            aurios: Cantidad de Aurios
            
        Returns:
            Valor en USD
        """
        return aurios * AURIO_VALUE_USD
    
    def validate_redeem_request(self, ambassador_id: str, aurios: int) -> Dict:
        """
        Valida una solicitud de canje de Aurios.
        
        Args:
            ambassador_id: ID del Embajador
            aurios: Cantidad de Aurios a canjear
            
        Returns:
            Dict con resultado de validación
        """
        if aurios < MINIMUM_REDEEM_AMOUNT:
            return {
                'valid': False,
                'error': f'Mínimo de {MINIMUM_REDEEM_AMOUNT} Aurios requerido'
            }
        
        # Verificar saldo del embajador
        balance = self.get_ambassador_balance(ambassador_id)
        if balance < aurios:
            return {
                'valid': False,
                'error': 'Saldo insuficiente'
            }
        
        return {'valid': True}
    
    def get_ambassador_balance(self, ambassador_id: str) -> int:
        """
        Obtiene el saldo actual de un Embajador.
        
        Args:
            ambassador_id: ID del Embajador
            
        Returns:
            Saldo en Aurios
        """
        # Query a base de datos
        result = self.db.execute(
            "SELECT balance FROM ambassadors WHERE id = ?",
            (ambassador_id,)
        ).fetchone()
        
        return result[0] if result else 0
    
    def process_redeem(self, ambassador_id: str, aurios: int, 
                       payment_method: str) -> Dict:
        """
        Procesa un canje de Aurios.
        
        Args:
            ambassador_id: ID del Embajador
            aurios: Cantidad de Aurios
            payment_method: Método de pago
            
        Returns:
            Dict con resultado del procesamiento
        """
        # Validar solicitud
        validation = self.validate_redeem_request(ambassador_id, aurios)
        if not validation['valid']:
            return validation
        
        # Calcular valor
        usd_value = self.calculate_aurio_value(aurios)
        
        # Crear transacción
        transaction_id = self.create_transaction(
            ambassador_id=ambassador_id,
            aurios=aurios,
            usd_value=usd_value,
            payment_method=payment_method
        )
        
        return {
            'success': True,
            'transaction_id': transaction_id,
            'aurios': aurios,
            'usd_value': usd_value
        }
    
    def create_transaction(self, ambassador_id: str, aurios: int,
                          usd_value: float, payment_method: str) -> str:
        """
        Crea una nueva transacción de canje.
        
        Args:
            ambassador_id: ID del Embajador
            aurios: Cantidad de Aurios
            usd_value: Valor en USD
            payment_method: Método de pago
            
        Returns:
            ID de la transacción
        """
        transaction_id = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.db.execute("""
            INSERT INTO transactions 
            (id, ambassador_id, aurios, usd_value, payment_method, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (transaction_id, ambassador_id, aurios, usd_value, 
              payment_method, datetime.now().isoformat()))
        
        self.db.commit()
        return transaction_id


def format_currency(amount: float, currency: str = 'USD') -> str:
    """
    Formatea una cantidad como moneda.
    
    Args:
        amount: Cantidad a formatear
        currency: Código de moneda
        
    Returns:
        String formateado
    """
    return f"{currency} ${amount:.2f}"
