"""
Mock Payment Microservice using Flask
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
import logging
import sys
from flask import Flask, request, jsonify
from controllers.payment_controller import add_payment, process_payment, get_payment

# Jaeger/OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = Flask(__name__)

# Configuration du logging pour afficher dans les logs Docker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Configuration Jaeger/OpenTelemetry
resource = Resource.create({
   "service.name": "payment-service",
   "service.version": "1.0.0"
})

trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# Configuration de l'exportateur Jaeger
otlp_exporter = OTLPSpanExporter(
   endpoint="http://jaeger:4317",
   insecure=True
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Instrumentation automatique Flask et Requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

@app.route("/")
def home():
    """Handle requests to base URL of the microservice """
    return jsonify({"service": "PaymentMicroservice", "status": "running"})

@app.route("/payments", methods=["POST"])
def post_add_payment():
    """Create a new payment"""
    with tracer.start_as_current_span("create-payment"):
        print("Endpoint: POST /payments")
        try:
            result = add_payment(request)
            return jsonify(result), 201
        except Exception as e:
            print(e)
            return jsonify({"error": str(e)}), 400

@app.route("/payments/process/<int:payment_id>", methods=["POST"])
def post_process_payment(payment_id):
    """Process a simulated credit card payment"""
    with tracer.start_as_current_span("process-payment"):
        print(f"Endpoint: POST /payments/process/{payment_id}")
        try:
            credit_card_data = request.get_json() or {}
            result = process_payment(payment_id, credit_card_data)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    
@app.route("/payments/<int:payment_id>", methods=["GET"])
def get_payment_details(payment_id):
    """Get payment details for a specific payment ID"""
    with tracer.start_as_current_span("get-payment"):
        try:
            payment_data = get_payment(payment_id)
            return jsonify(payment_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 404

@app.errorhandler(404)
def handle_404(error):
    """Handle 404 errors with JSON response"""
    print(error)
    return jsonify({"error": "Endpoint ou ressource introuvable"}), 404

# Start Flask app
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5009, debug=True)