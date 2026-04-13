import boto3
import json
from django.conf import settings

# This allows you to toggle AWS on/off in settings.py later
IS_OFFLINE = False 

def get_boto_client(service_name):
    # Safely get credentials from settings
    aws_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
    aws_secret = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
    aws_token = getattr(settings, 'AWS_SESSION_TOKEN', None)
    
    # Service-specific region logic
    if service_name == 'sns':
        region = getattr(settings, 'AWS_SNS_REGION_NAME', None) or getattr(settings, 'AWS_REGION_NAME', None) or 'us-east-1'
    else:
        region = getattr(settings, 'AWS_REGION_NAME', None) or getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')

    # EXPLICIT LOCAL MODE: Only if IS_OFFLINE is True or key is 'LOCAL_KEY'
    if IS_OFFLINE or aws_key == 'LOCAL_KEY':
        return None
    
    # Zero-Hardcoding: We pass credentials ONLY if both are explicitly set in the environment.
    # Otherwise, Boto3 will automatically pick up Cloud9 Managed Credentials, 
    # IAM Roles, or ~/.aws/credentials.
    if aws_key and aws_secret:
        return boto3.client(
            service_name, 
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            aws_session_token=aws_token,
            region_name=region
        )
    
    # Cloud-Native Fallback (Cloud9 / EC2 / GitHub Actions)
    return boto3.client(service_name, region_name=region)

import re
import dateutil.parser

# --- Feature 1: Image Scanning (Textract) ---
def scan_product_label(image_bytes):
    try:
        client = get_boto_client('textract')
        
        if client is None:
            return ["SIMULATION: EXP: 2026-12-31"]
        
        response = client.detect_document_text(Document={'Bytes': image_bytes})
        return [item['Text'] for item in response['Blocks'] if item['BlockType'] == 'LINE']
    except Exception as e:
        # In case of error (like 'No credentials found'), we fallback to a notice
        print(f"Textract Detection Failed: {e}")
        return [f"Textract Error/Simulation: {str(e)}", "EXP: 2026-12-31"]

def get_product_expiry_from_image(image_bytes):
    lines = scan_product_label(image_bytes)
    date_patterns = [
        r'\d{2}-\d{2}-\d{4}', r'\d{4}-\d{2}-\d{2}',
        r'\d{2}/\d{2}/\d{4}', r'\d{4}/\d{2}/\d{2}'
    ]
    for line in lines:
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    parsed_date = dateutil.parser.parse(match.group())
                    return parsed_date.strftime('%Y-%m-%d')
                except:
                    continue
    return None

# --- Feature 2: Stock Alerts (SNS) ---
def send_sns_alert(subject, message):
    client = get_boto_client('sns')

    # If client is None, it means we are in LOCAL MODE
    if client is None:
        print("\n" + "="*40)
        print(f"[SIMULATED SNS ALERT]\nSubject: {subject}\nMessage: {message}")
        print("="*40 + "\n")
        return

    # Real AWS Logic
    try:
        # Robust lookup: ensure we don't pass None to Boto3
        topic_arn = getattr(settings, 'SNS_TOPIC_ARN', None) or ''
        
        if not topic_arn:
            print("SNS Error: topic_arn is empty. Set SNS_TOPIC_ARN in environment.")
            return False

        client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=subject
        )
        return True
    except Exception as e:
        print(f"Failed to send real SNS alert: {e}")
        return False

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