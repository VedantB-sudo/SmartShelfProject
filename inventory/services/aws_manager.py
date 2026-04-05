import boto3
import json
from django.conf import settings

# This allows you to toggle AWS on/off in settings.py later
IS_OFFLINE = True 

def get_boto_client(service_name):
    # Safely get credentials or use 'LOCAL_KEY' as a fallback
    aws_key = getattr(settings, 'AWS_ACCESS_KEY_ID', 'LOCAL_KEY')
    aws_secret = getattr(settings, 'AWS_SECRET_ACCESS_KEY', 'LOCAL_SECRET')
    region = getattr(settings, 'AWS_REGION_NAME', 'us-east-1')

    if IS_OFFLINE or aws_key == 'LOCAL_KEY':
        return None
    
    return boto3.client(
        service_name, 
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=region
    )

# --- Feature 1: Image Scanning (Rekognition) ---
def scan_product_label(image_bytes):
    client = get_boto_client('rekognition')
    
    if client is None:
        return ["LOCAL MODE: Label scanning simulated. Text: 'Sample Product 123'"]
    
    try:
        response = client.detect_text(Image={'Bytes': image_bytes})
        return [text['DetectedText'] for text in response['TextDetections'] if text['Type'] == 'LINE']
    except Exception as e:
        return [f"Rekognition Error: {str(e)}"]

# --- Feature 2: Stock Alerts (SNS) ---
def send_low_stock_notification(product_name, qty):
    message = f"CRITICAL STOCK ALERT: {product_name} has fallen to {qty} units. Please reorder immediately."
    
    client = get_boto_client('sns')

    # If client is None, it means we are in LOCAL MODE
    if client is None:
        print("\n" + "="*40)
        print(f"[SIMULATED SNS ALERT]\n{message}")
        print("="*40 + "\n")
        return

    # Real AWS Logic
    try:
        topic_arn = getattr(settings, 'SNS_TOPIC_ARN', '')
        client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject="SmartShelf Low Stock Warning"
        )
    except Exception as e:
        print(f"Failed to send real SNS alert: {e}")

# --- Feature 3: AI Insights (Bedrock) ---
def get_inventory_advice(data_summary):
    client = get_boto_client('bedrock-runtime')
    
    if client is None:
        # This is what shows on your dashboard right now
        return f"SmartShelf AI Insight: {data_summary} I recommend prioritizing orders for items below 5 units."
    
    try:
        # Logic for Bedrock (Claude or Titan) would go here in production
        return "AI analysis complete (Live Mode)."
    except Exception as e:
        return f"AI Assistant currently unavailable: {e}"

# --- Feature 4: Report Generation (Lambda) ---
def trigger_lambda_pdf(inventory_data):
    client = get_boto_client('lambda')

    # LOCAL SIMULATION
    if client is None:
        print("\n" + "!"*40)
        print("--- AWS LAMBDA SIMULATION ---")
        print(f"Data received from Django: {len(inventory_data)} products.")
        print(f"Payload Snapshot: {json.dumps(inventory_data[:2], indent=2)}...") 
        print("!"*40 + "\n")
        return None 

    # REAL AWS CALL
    try:
        response = client.invoke(
            FunctionName='SmartShelf_PDF_Generator',
            InvocationType='RequestResponse',
            Payload=json.dumps(inventory_data)
        )
        response_payload = json.loads(response['Payload'].read())
        return response_payload.get('s3_url')
    except Exception as e:
        print(f"Lambda Error: {e}")
        return None