'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
import json
from aws_lambda_typing import context as context_, events, responses
from aws_lambda_typing.common.iam import PolicyDocument, Statement, Principal
import jwt
import os
import sys
import json
import logging
_top_logger = logging.getLogger("py-authorizer")
# if not _top_logger.hasHandlers():
#         _top_logger.addHandler(logging.StreamHandler(stream=sys.stdout))


def lambda_handler(
        event: events.APIGatewayRequestAuthorizerEvent,
        context:context_.Context) -> responses.api_gateway_authorizer.APIGatewayAuthorizerResponse :
    ''' AWS Authorizer entry point. 
    details on event parameter can be found at:
    - https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-input.html

    details on expected response can be found at:
    - https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-output.html

    details on context parameter can be found at:
    - https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
    - https://github.com/aws/aws-lambda-python-runtime-interface-client/blob/main/awslambdaric/lambda_context.py 
    '''
    # temp_debug_jwks = '{"keys":[{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": "263d2617-aa94-4599-9b67-9faec4389d3c", "n": "w-W6LzWoIbU1z5_A5J85VZQsJ_4xFT4A-dtr3TPiFb5hfiqY4JWVsZ4Aao5o9TVTdX8vl7cQWskHs3F1YnrRE815SqW257QZHSqUe3tZC9koQVcqNS8xIisXwNFx4GR7gGIb-6eAhuqXS-S_h-exzWvIAWI5AAGvi4i2kp3ahWZbKos4P-i6lGUoEbePGAQ9yp-IVTsYEOP5wHh29dPcpqnl4zix4TFUgl8xCo_gIlwfAk-SZmiXk_ePksZU3fMLYDzCGjx_BWlI1OF9blZmlmvmCjYRcTE0de5soH_azxLYJqGc847OlakMmyBXYmyZ955X6KVj5dcXT3czLIiF1Q", "e": "AQAB"}]}'
    temp_debug_jwks = None

    decision:str = "Deny"
    # we'll look up for JWT in the Authorization http-header
    http_headers = event.get("headers", {})
    bearer = http_headers.get("Authorization", http_headers.get("authorization", None))
    # _top_logger.debug(f"Collect token {bearer[7:17] if isinstance(bearer,str) else 'NONE'}")

    if isinstance(bearer, str) and bearer.startswith("Bearer "):
        # we need to remove "Bearer " prefix to have the JWT
        bearer = bearer[7:]
        # we'll validate token against trusted IdP
        # values are available in stage variables
        all_stage_variables = event.get("stageVariables", {})
        jwt_audience = all_stage_variables.get("jwtAudience", None)
        jwt_issuer =  all_stage_variables.get("jwtIssuer", None)
        jwks_url = all_stage_variables.get("jwksUrl", None)
        # collect token claims
        decision = "Allow"
        data = {}
        try:
            # we'll check claims first and only if Ok will check the signature (signature )
            unverified_claimset = jwt.decode(bearer, options={"verify_signature": False})
            if isinstance(unverified_claimset, dict):
                if unverified_claimset.get("iss", None) != jwt_issuer:
                    _top_logger.warning(f"Token issuer is not right. {unverified_claimset.get('iss', None)}!={jwt_issuer}")
                    decision = "Deny"
                elif unverified_claimset.get("aud", None) != jwt_audience:
                    _top_logger.warning(f"Token audience is not right")
                    decision = "Deny"
            kid = unverified_claimset.get("header", {}).get("kid", None)
        except Exception as e:
            _top_logger.error(f"FAIL to collect claims from token with exception {e}")
            decision = "Deny"

        if decision == "Allow":
            try:
                # aud and iss claims were validated - let's check the signature and date/time claims
                # we need to collect public key first
                # normally it'll be the call to IdP jwks endpoint (value is a part of trusted configuration - jwks_url)
                # for the purpose of our performance testing we have jwks endpoint response already available in the env var
                jwks_response = json.loads(os.getenv("jwksResponse") or temp_debug_jwks)
                jwk_set = jwt.PyJWKSet.from_dict(jwks_response)
                signing_keys = [
                    jwk_set_key
                    for jwk_set_key in jwk_set.keys
                    if jwk_set_key.public_key_use in ["sig", None] and (jwk_set_key.key_id==kid if kid else True)
                ]
                if len(signing_keys)!=1:
                    message = "Was not able to collect right public key from jwks response"
                    _top_logger.error(message)
                    raise ValueError(message)
                signing_key = signing_keys[0]
                
                data = jwt.decode(
                    bearer,
                    signing_key.key,
                    algorithms=["RS256"],   # it's hardcoded per RFC 8725 §2.1 recommendation 
                    # issuer=jwt_issuer, # Note that we already verified 'iss' so can skip validation here
                    # audience=jwt_audience, # Note that we already verified 'aud' so can skip validation here
                    require=["exp"],    # aud and iss already validated, iat and nbf are optional
                    options={
                        "verify_aud": False,    # verified already
                        "verify_iss": False,    # verified already
                        "verify_exp": True,
                        "verify_nbf": True,
                        "verify_iat": True,
                    },
                )
            except jwt.ExpiredSignatureError as e:
                _top_logger.error(f"JWT expired {e}")
                decision = "Deny"
            except jwt.InvalidIssuedAtError as e:
                _top_logger.error(f"JWT 'issued at' is invalid {e}")
                decision = "Deny"
            except Exception as e:
                _top_logger.error(f"FAIL to validate token with exception {e}")
                decision = "Deny"
    else:
        # we don't have token
        _top_logger.warning(f"No token found")

    method_arn = event["methodArn"].split("/")
    decision_policy = responses.api_gateway_authorizer.APIGatewayAuthorizerResponse(
        principalId="some",
        policyDocument=PolicyDocument(
            Version='2012-10-17',
            Statement=[
                Statement(
                    Action="execute-api:Invoke",
                    Effect=decision,
                    #! NOTE that using "*" for resources is not a best practice!
                    #! Using incoming method_arn is also not good as it'll result in incorrect cached authorizer responses
                    #! You should specify list of resources per authorizer in real API
                    #! But our is just a test so we'll be using "*"
                    Resource=f"{method_arn[0]}/{method_arn[1]}/GET/*"
                )
            ]
        ),
        context=data if isinstance(data, dict) else {}
    )
    # _top_logger.debug(f"Decision policy is \n{json.dumps(decision_policy, indent=2)}")
    return decision_policy

'''
if __name__=="__main__":

    print(lambda_handler( {
        "type": "REQUEST",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/api/GET/request",
        "resource": "/request",
        "path": "/request",
        "httpMethod": "GET",
        "headers": {
            "X-AMZ-Date": "20170718T062915Z",
            "Accept": "*/*",
            "HeaderAuth1": "headerValue1",
            "CloudFront-Viewer-Country": "US",
            "CloudFront-Forwarded-Proto": "https",
            "CloudFront-Is-Tablet-Viewer": "false",
            "CloudFront-Is-Mobile-Viewer": "false",
            "User-Agent": "...",
            "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IjI2M2QyNjE3LWFhOTQtNDU5OS05YjY3LTlmYWVjNDM4OWQzYyIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL0FwaUd3TGF0ZW5jeVRlc3RJc3N1ZXIiLCJhdWQiOiJBcGlHd0xhdGVuY3lUZXN0QXVkaWVuY2UiLCJpYXQiOjE3MDg5ODA1MDQsImV4cCI6MTcwOTAyMzcwNCwibmJmIjoxNzA4OTgwNTA0fQ.tFR58xOQuGuuTVLCmS4GKLrxqw7L02ydqWzIKcbHq-U1zVCugKShMrKYWAUQVwqp6ny7J_Zc7Fqp1IAEuSxL2StQwoA8kjuI5AAZKygJVXmr3SHCBS064O2T6d66KHlXxXyRu17PV4GBixxSI2ZPuiQjICc9SXwK5q0U1JkyLV2TcrUhghGWdK-2Mq3IraGDuQgxKMAuEJH621pWVAppR58xxfp8e0gO--pJ1mnl4Rlt1CF1ymtWwQtv7HXQLQ5L4sAx5_RMTMbFILLu0JlGEjXeUseNAHy6vsXREOuDsbTS_6swg4iCqLXGPg1E_iN9n23iY50FY2EAUH3BrsWkLA"
        },
        "queryStringParameters": {
            "QueryString1": "queryValue1"
        },
        "pathParameters": {},
        "stageVariables": {
            "jwtAudience": 'ApiGwLatencyTestAudience',
            "jwtIssuer": 'https://ApiGwLatencyTestIssuer',
            "jwksUrl": 'https://testIssuer/jwks.json'
        },
        "requestContext": {
            "path": "/request",
            "accountId": "123456789012",
            "resourceId": "05c7jb",
            "stage": "api",
            "requestId": "...",
            "identity": {
            "apiKey": "...",
            "sourceIp": "...",
            "clientCert": {
                "clientCertPem": "CERT_CONTENT",
                "subjectDN": "www.example.com",
                "issuerDN": "Example issuer",
                "serialNumber": "a1:a1:a1:a1:a1:a1:a1:a1:a1:a1:a1:a1:a1:a1:a1:a1",
                "validity": {
                "notBefore": "May 28 12:30:02 2019 GMT",
                "notAfter": "Aug  5 09:36:04 2021 GMT"
                }
            }
            },
            "resourcePath": "/request",
            "httpMethod": "GET",
            "apiId": "abcdef123"
        }
        }, {} ))
'''