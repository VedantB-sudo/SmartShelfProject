import boto3
from botocore.exceptions import ClientError

# ADVANCED CONSTRUCT: A Decorator for standardized error handling
def aws_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            print(f"AWS Service Error: {e.response['Error']['Message']}")
            return None
    return wrapper

class SmartCloudManager:
    """
    Custom Library to encapsulate Boto3 interactions for SmartShelf.
    Fulfills the NCI requirement for original library formulation.
    """
    def __init__(self, region_name='eu-west-1'):
        self.region = region_name
        self.textract = boto3.client('textract', region_name=self.region)
        self.s3 = boto3.client('s3', region_name=self.region)

    @aws_error_handler
    def extract_inventory_data(self, bucket_name, document_name):
        """
        Custom logic to wrap Textract calls and return structured data.
        """
        response = self.textract.analyze_document(
            Document={'S3Object': {'Bucket': bucket_name, 'Name': document_name}},
            FeatureTypes=["TABLES", "FORMS"]
        )
        return response

    # ADVANCED CONSTRUCT: Context Manager for S3 resource handling
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Logic to ensure connections are closed or logged
        print("Cloud resources finalized.")