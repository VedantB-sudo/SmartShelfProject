import os
import logging
from datetime import datetime
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute, 
    NumberAttribute, 
    UTCDateTimeAttribute, 
    JSONAttribute
)
from django.core.mail import send_mail
from django.conf import settings

# Set up logging to track SES email status
logger = logging.getLogger(__name__)

class Product(Model):
    """
    DynamoDB Model for SmartShelf Inventory.
    This replaces the standard Django relational model.
    """
    class Meta:
        # Matches the table name in your AWS Console
        table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'SmartShelf_Inventory')
        region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Credentials for NCI Learner Lab
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_session_token = os.environ.get('AWS_SESSION_TOKEN')

    # Attributes (DynamoDB Schema)
    # Using 'sku' as the Hash Key (Primary Key) to match DynamoDB table schema
    sku = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute()
    category = UnicodeAttribute()
    quantity = NumberAttribute(default=0)
    price = NumberAttribute()
    expiry_date = UnicodeAttribute()  # DynamoDB stores dates as strings or numbers
    image_url = UnicodeAttribute(null=True) # S3 URL path
    last_audited = UTCDateTimeAttribute(default=datetime.now)

    @property
    def calculated_status(self):
        """Logic for the Dashboard status badges"""
        if self.quantity <= 2:
            return "Critical"
        elif self.quantity <= 5:
            return "Attention"
        return "Fresh"

    def save(self, **kwargs):
        """
        Overrides the PynamoDB save method to trigger SNS alerts 
        automatically when stock falls below threshold.
        """
        from .services import aws_manager
        
        if self.quantity < 5:
            subject = f"⚠️ SmartShelf Alert: Low Stock on {self.name}"
            message = (
                f"INVENTORY ALERT\n"
                f"--------------------------\n"
                f"Product: {self.name}\n"
                f"Current Stock: {self.quantity}\n"
                f"Status: {self.calculated_status}\n"
                f"Category: {self.category}\n\n"
                f"Action Required: Please restock this item immediately via the dashboard."
            )
            aws_manager.send_sns_alert(subject, message)
            
        return super(Product, self).save(**kwargs)