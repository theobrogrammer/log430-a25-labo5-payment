"""
Payment controller
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
import numbers
import logging
import requests
from commands.write_payment import create_payment, update_status_to_paid
from queries.read_payment import get_payment_by_id
from config import KRAKEND_URL

# Import OpenTelemetry pour le tracing
from opentelemetry import trace

# Configuration du logger avec un nom spécifique
logger = logging.getLogger('payment_controller')
logger.setLevel(logging.INFO)

# Récupération du tracer pour ce module
tracer = trace.get_tracer(__name__)

def get_payment(payment_id):
    return get_payment_by_id(payment_id)

def add_payment(request):
    """ Add payment based on given params """
    with tracer.start_as_current_span("add-payment-operation"):
        payload = request.get_json() or {}
        user_id = payload.get('user_id')
        order_id = payload.get('order_id')
        total_amount = payload.get('total_amount')
        result = create_payment(order_id, user_id, total_amount)
        if isinstance(result, numbers.Number):
            return {"payment_id": result}
        else:
            return {"error": str(result)}
    
def process_payment(payment_id, credit_card_data):
    """ Process payment with given ID, notify store_manager sytem that the order is paid """
    with tracer.start_as_current_span("process-payment-operation"):
        # S'il s'agissait d'une véritable API de paiement, nous enverrions les données de la carte de crédit à un 
        # payment gateway (ex. Stripe, Paypal) pour effectuer le paiement. Cela pourrait se trouver dans un microservice distinct.
        _process_credit_card_payment(credit_card_data)

        # Si le paiement est réussi, mettre à jour les statut de la commande
        # Ensuite, faire la mise à jour de la commande dans le Store Manager (en utilisant l'order_id)
        update_result = update_status_to_paid(payment_id)
        logger.info(f"Updated order {update_result['order_id']} to paid={update_result}")
        
        # Notifier le Store Manager que le paiement a été effectué
        notification_result = _notify_store_manager(update_result['order_id'], payment_id)
        
        result = {
            "order_id": update_result["order_id"],
            "payment_id": update_result["payment_id"],
            "is_paid": update_result["is_paid"],
            "store_notified": notification_result
        }

        return result
    
def _process_credit_card_payment(payment_data):
    """ Placeholder method for simulated credit card payment """
    logger.debug(f"Processing credit card: {payment_data.get('cardNumber')}")
    logger.debug(f"Card code: {payment_data.get('cardCode')}")
    logger.debug(f"Expiration date: {payment_data.get('expirationDate')}")

def _notify_store_manager(order_id, payment_id):
    with tracer.start_as_current_span("notify-store-manager"):
        try:
            # Construire l'URL pour appeler KrakenD qui routera vers le Store Manager
            # Store Manager attend PUT /orders (SANS l'ID dans l'URL)
            # L'order_id est envoyé dans le payload
            notification_url = f"{KRAKEND_URL}/store-api/orders"
            
            # Préparer les données pour mettre à jour is_paid à true
            # Inclure order_id dans le payload car Store Manager l'attend là
            payload = {
                "order_id": order_id,
                "is_paid": True
            }
            
            # Envoyer la requête PUT au Store Manager via KrakenD
            logger.info(f"Calling KrakenD to update order {order_id} at {notification_url}")
            response = requests.put(
                notification_url,
                json=payload,
                timeout=5  # Timeout de 5 secondes
            )
            
            # Vérifier si la mise à jour a réussi
            if response.status_code in [200, 201, 204]:
                logger.info(f"Order {order_id} successfully updated via KrakenD (status: {response.status_code})")
                return True
            else:
                logger.warning(f"Failed to update order {order_id} via KrakenD (status: {response.status_code})")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while calling KrakenD for order {order_id}")
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error while calling KrakenD for order {order_id}")
            return False
        except Exception as e:
            logger.error(f"Error calling KrakenD to update order: {str(e)}")
            return False