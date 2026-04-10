import boto3
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class AWSManager:
    """
    Handles interactions with AWS services including SNS for alerts,
    Textract for document analysis, and IoT telemetry logic.
    """
    def __init__(self):
        # Initialize the SNS client using settings from settings.py
        self.sns_client = boto3.client(
            'sns', 
            region_name=getattr(settings, 'AWS_SNS_REGION_NAME', 'us-east-1')
        )

    def send_low_stock_alert(self, product_name, quantity):
        """
        Publishes a message to the SNS Topic. 
        Anyone subscribed to the Topic ARN will receive the alert.
        """
        message = f"SmartShelf Alert: '{product_name}' is running low with only {quantity} units remaining."
        subject = "Low Stock Notification"

        try:
            response = self.sns_client.publish(
                TopicArn=settings.SNS_TOPIC_ARN,
                Message=message,
                Subject=subject
            )
            return response['MessageId']
        except Exception as e:
            logger.error(f"SNS Publish Error: {str(e)}")
            return None

    def get_inventory_advice(self, summary):
        """
        Abstracted logic for inventory optimization and IoT thermal monitoring.
        """
        return f"System Analysis: {summary}. Recommendation: Activate thermal monitoring for perishable goods."

# Instantiate the manager for use in views.py
aws_manager = AWSManager()