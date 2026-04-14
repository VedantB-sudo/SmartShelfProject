import os
import logging
from datetime import datetime
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute, 
    NumberAttribute, 
    UTCDateTimeAttribute, 
    JSONAttribute,
    BooleanAttribute
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
    shelf_number = UnicodeAttribute(null=True) # Physical location on shelf
    is_perishable = BooleanAttribute(default=False)
    current_temperature = NumberAttribute(null=True) # Perishable goods tracking
    temp_threshold = NumberAttribute(default=15.0) # High temp alert trigger
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
        from .services import aws_manager
        
        # Save the product first
        res = super(Product, self).save(**kwargs)

        # Formatted Low Stock Alert
        try:
            if int(self.quantity) < 5:
                subject = f"🔔 SmartShelf: Low Stock Alert - {self.name}"
                
                # Using triple quotes for a clean, multi-line email format
                message = f"""
Hello,

This is an automated alert from your SmartShelf Intelligent Inventory System.

PRODUCT DETAILS:
-------------------------------
Item Name:    {self.name}
Current Stock: {self.quantity}
Threshold:     5 units
Status:        LOW STOCK

Please restock this item soon to avoid inventory depletion.

View Dashboard: http://smartcloud.us-east-1.elasticbeanstalk.com/dashboard/
-------------------------------
SmartShelf Cloud-Native System
                """
                
                aws_manager.send_sns_alert(subject, message.strip())
        except Exception as e:
            print(f"SNS failed: {e}")
        
        return res

        # 2. Thermal Alert (Perishables only)
        if self.is_perishable and self.current_temperature is not None:
             if self.current_temperature > self.temp_threshold:
                 subject = f"🔥 SmartShelf CRITICAL: High Temperature on {self.name}"
                 message = (
                     f"THERMAL SENSOR ALERT\n"
                     f"--------------------------\n"
                     f"Product: {self.name}\n"
                     f"Sensor Reading: {self.current_temperature}°C\n"
                     f"Safe Threshold: {self.temp_threshold}°C\n\n"
                     f"URGENT: Check cooling system or shelf placement."
                 )
                 aws_manager.send_sns_alert(subject, message)

        # 3. Expiry Alert (Near-perish notifications)
        try:
            from dateutil import parser
            from datetime import date
            if self.expiry_date and self.expiry_date != "Unknown":
                expiry_dt = parser.parse(self.expiry_date).date()
                days_left = (expiry_dt - date.today()).days
                
                if 0 <= days_left <= 3:
                    subject = f"⏳ SmartShelf Alert: {self.name} is about to perish"
                    message = (
                        f"EXPIRY ALERT\n"
                        f"--------------------------\n"
                        f"Product: {self.name}\n"
                        f"Expiry Date: {self.expiry_date}\n"
                        f"Days Remaining: {days_left}\n\n"
                        f"Action: Please prioritize usage or discount this item."
                    )
                    aws_manager.send_sns_alert(subject, message)
        except Exception as e:
            logger.error(f"Error checking expiry date for SNS: {e}")
            
        return super(Product, self).save(**kwargs)