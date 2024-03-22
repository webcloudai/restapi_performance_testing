'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
import json
from time import sleep
import boto3
from uuid import uuid4

def lambda_handler(event:dict, context):
    ''' AWS Lambda entry point. Transform event and context to consumable by microservice_logic 
    details on event parameter can be found at:
    - https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-concepts.html#gettingstarted-concepts-event
    - https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html#apigateway-example-event
    - https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html
    - https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html
    - https://docs.aws.amazon.com/lambda/latest/dg/lambda-services.html (see event info for each service)

    details on context parameter can be found at:
    - https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
    - https://github.com/aws/aws-lambda-python-runtime-interface-client/blob/main/awslambdaric/lambda_context.py 
    '''
    sleep(0.3)
    # serialize event
    try:
        eventStr = json.dumps(event)
    except Exception as e:
        return {"statusCode": 500, "body": "fail to serialize event", "isBase64Encoded": False}

    # bucket name and object key
    try:
        test_bucket_name = event["stageVariables"]["testBucketName"]
    except Exception as e:
        return {"statusCode": 500, "body": "fail to collect bucket name", "isBase64Encoded": False}
    obj_key = f"{uuid4()}.json"
    # put object to bucket
    s3_client = boto3.client("s3")
    try:
        s3_client.put_object(Body=eventStr, Bucket=test_bucket_name, Key=obj_key)
    except Exception as e:
        return {"statusCode": 500, "body": "fail to to put object to bucket", "isBase64Encoded": False}
    sleep(0.1)
    # delete object from bucket
    try:
        s3_client.delete_object(Bucket=test_bucket_name, Key=obj_key)
    except Exception as e:
        return {"statusCode": 500, "body": "fail to to delete object from bucket", "isBase64Encoded": False}
    
    result = {
        "statusCode": 200,
        "body": eventStr,
        "isBase64Encoded": False
    }
    return result
