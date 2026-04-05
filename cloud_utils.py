import boto3
import logging
from botocore.exceptions import ClientError

# Set up logging for CloudWatch/EB Logs
logger = logging.getLogger(__name__)

# ADVANCED CONSTRUCT: A Decorator for standardized error handling across all AWS services
def aws_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            error_msg = e.response['Error']['Message']
            logger.error(f"AWS Service Error in {func.__name__}: {error_msg}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            return None
    return wrapper

class SmartCloudManager:
    """
    Comprehensive Library to encapsulate Boto3 interactions for SmartShelf.
    Supports S3, Textract, DynamoDB, and SES.
    """
    def __init__(self, region_name='eu-west-1'):
        self.region = region_name
        self.textract = boto3.client('textract', region_name=self.region)
        self.s3 = boto3.client('s3', region_name=self.region)
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.ses = boto3.client('ses', region_name=self.region)

    # --- S3 & TEXTRACT LOGIC ---
    @aws_error_handler
    def process_inventory_document(self, bucket_name, document_name):
        """
        Coordinates document analysis using Amazon Textract.
        """
        response = self.textract.analyze_document(
            Document={'S3Object': {'Bucket': bucket_name, 'Name': document_name}},
            FeatureTypes=["FORMS"]
        )
        return self._parse_textract_response(response)

    def _parse_textract_response(self, response):
        """
        PRIVATE METHOD: Transforms raw JSON into structured inventory objects.
        """
        if not response: return {}
        extracted_data = {}
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '')
                if ':' in text:
                    key, value = text.split(':', 1)
                    extracted_data[key.strip().lower()] = value.strip()
        return extracted_data

    # --- DYNAMODB LOGIC ---
    @aws_error_handler
    def update_inventory_stock(self, table_name, item_id, quantity):
        """
        Persists inventory updates to Amazon DynamoDB.
        """
        table = self.dynamodb.Table(table_name)
        table.update_item(
            Key={'item_id': item_id},
            UpdateExpression="set stock_count = stock_count + :val",
            ExpressionAttributeValues={':val': quantity}
        )
        logger.info(f"DynamoDB updated for item {item_id}.")

    # --- SES ALERT LOGIC ---
    @aws_error_handler
    def send_low_stock_alert(self, recipient, item_name):
        """
        Triggers automated email notifications via Amazon SES.
        """
        self.ses.send_email(
            Source='noreply@smartshelf.com',
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': f'Low Stock Alert: {item_name}'},
                'Body': {'Text': {'Data': f'The inventory for {item_name} is below the threshold.'}}
            }
        )

    # --- ADVANCED CONSTRUCT: Context Manager ---
    def __enter__(self):
        logger.info("Initializing SmartCloudManager session...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Session closed with error: {exc_val}")
        else:
            logger.info("Cloud resources finalized successfully.")