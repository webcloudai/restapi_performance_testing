'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from __future__ import annotations
from aws_cdk import (
    Duration, RemovalPolicy,
    Stack,
    aws_s3,
    aws_lambda,
    aws_apigateway,
    aws_cloudwatch,
    aws_logs,
    aws_iam,
)
from constructs import Construct
from typing import Union, Dict, List
from pathlib import Path
from enum import Enum
import logging
_top_logger = logging.getLogger(__name__)

class LANG(Enum):
    PYTHON = "py"
    JAVA = "java"
    NODEJS = "nodejs"
    DOTNET = "dotnet"
    DOTNETCORE = "dotcore"
    GO = "go"
    RUST = "rust"
    CSHARP = "csharp"
    C = "c"
    CPP = "cpp"
    FORTRAN = "fortran"
    RUBY = "ruby"
    TYPESCRIPT = "ts"
    OTHER = "other"

    @staticmethod
    def byValue(value:str) -> LANG:
        for lang in LANG:
            if lang.value == value:
                return lang
        raise ValueError(f"Unknown language value '{value}'")

class RUNTIME(Enum):
    PYTHON = aws_lambda.Runtime.PYTHON_3_12
    JAVA = aws_lambda.Runtime.JAVA_21
    NODEJS = aws_lambda.Runtime.NODEJS_20_X
    DOTNET = aws_lambda.Runtime.DOTNET_6
    DOTNETCORE = aws_lambda.Runtime.DOTNET_CORE_3_1
    GO = aws_lambda.Runtime.PROVIDED_AL2023
    RUST = aws_lambda.Runtime.PROVIDED_AL2023
    CSHARP = aws_lambda.Runtime.DOTNET_CORE_3_1
    C = aws_lambda.Runtime.PROVIDED_AL2023
    CPP = aws_lambda.Runtime.PROVIDED_AL2023
    FORTRAN = aws_lambda.Runtime.PROVIDED_AL2023
    RUBY = aws_lambda.Runtime.RUBY_3_2
    TYPESCRIPT = aws_lambda.Runtime.NODEJS_20_X

class HANDLER(Enum):
    PYTHON = "lambda_code.lambda_handler"
    GO = "bootstrap"
    TYPESCRIPT = "index.lambdaHandler"
    #---
    JAVA = "LambdaHandler"
    NODEJS = "handler"
    DOTNET = "Lambda::FunctionHandler"
    DOTNETCORE = "Lambda::FunctionHandler"
    RUST = "bootstrap"
    CSHARP = "Lambda::FunctionHandler"
    C = "bootstrap"
    CPP = "bootstrap"
    FORTRAN = "bootstrap"
    RUBY = "lambda_handler"

class SIZE(Enum):
    MB128 = 128
    MB512 = 512
    MB1024 = 1024
    MD1536 = 1536
    MB2048 = 2048

    @staticmethod
    def smallest() -> SIZE:
        return SIZE.MB128
    
class ACCESS(Enum):
    PUBLIC = "public"
    IAM = "iam"
    JWT = "jwt"
    JWTCACHED = "jwtcached"

class ApplicationStack(Stack):

    lambda_constructs:Dict[str, Dict[str, aws_lambda.Function]]
    lambda_codes:Dict[LANG, Dict[str, aws_lambda.Code]]
    s3_bucket_construct:aws_s3.Bucket
    api_construct:aws_apigateway.RestApi
    access:ACCESS
    authorization_type:aws_apigateway.AuthorizationType
    authorizers:Dict[SIZE, aws_apigateway.RequestAuthorizer]

    def __init__(
            self, scope: Construct, construct_id: str,
            access_type:ACCESS,
            iam_invocation_role:aws_iam.Role,
            simulated_jwks_response:str,
            lambda_packages_location:Path=Path("deploy_lambda"),
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.iam_invocation_role = iam_invocation_role
        self.access=access_type
        self.authorization_type:aws_apigateway.AuthorizationType = aws_apigateway.AuthorizationType.NONE
        self.authorizers:Dict[SIZE, aws_apigateway.RequestAuthorizer] = {}
        # we'll use ONE log group for all lambdas to decrease number of resources
        # NOTE that this is NOT a best practice !
        lambdas_log_group = aws_logs.LogGroup(
            self, f"lambdas-log-group-{construct_id}",
            log_group_name=f"lambdas-log-group-{construct_id}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=aws_logs.RetentionDays.ONE_DAY
        )
        api_execution_log_group = aws_logs.LogGroup(
            self, f"API-Gateway-Execution-Logs_{construct_id}",
            log_group_name=f"API-Gateway-Execution-Logs_{construct_id}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=aws_logs.RetentionDays.ONE_DAY
        )
        # we'll identify authorization type of this stack and create authorizers if needed
        match self.access:
            case ACCESS.PUBLIC:
                _top_logger.info(f"API will be accessible by public")
                # we have nothing to do here
            case ACCESS.IAM:
                _top_logger.info(f"API will be accessible by IAM")
                self.authorization_type = aws_apigateway.AuthorizationType.IAM
                # we also need to add permissions to invoke this API to the role provided
                # but we'll do that when API defined

            case ACCESS.JWT:
                _top_logger.info(f"API will be accessible by JWT")
                self.authorization_type = aws_apigateway.AuthorizationType.CUSTOM
                # we have to define our custom Authorizers
                for size in SIZE:
                    authorizer_clean_name = f"py-authorizer_lambda"
                    authorizer_name = f"{authorizer_clean_name}-{size.value}-{construct_id}"
                    self.authorizers[size] = aws_apigateway.RequestAuthorizer(
                        self, f"authorizer{authorizer_name}",
                        identity_sources=[aws_apigateway.IdentitySource.header("Authorization")],
                        authorizer_name=f"{authorizer_name}-{construct_id}",
                        # this Authorizer responses will NOT be cached
                        results_cache_ttl=Duration.seconds(0),
                        handler=aws_lambda.Function(
                            self, f"lambda{authorizer_name}",
                            function_name=f"{authorizer_name}",
                            runtime=RUNTIME.PYTHON.value,
                            handler=HANDLER.PYTHON.value,
                            memory_size=size.value,
                            timeout=Duration.seconds(10),
                            architecture=aws_lambda.Architecture.ARM_64,
                            code=aws_lambda.Code.from_asset(
                                str(lambda_packages_location / f"{authorizer_clean_name}-deployment-package.zip"),
                            ),
                            application_log_level="INFO",
                            log_format="JSON",
                            system_log_level="INFO",
                            log_group=lambdas_log_group,
                            environment={ 
                                #! jwksResponse env variable will have "simulated JWKS response" including kid and public key
                                #! DO NOT USE THIS PATTERN IN REAL API! Call jwks endpoint of your IdP
                                "jwksResponse": simulated_jwks_response,
                            },
                        )
                    )
            case ACCESS.JWTCACHED:
                _top_logger.info(f"API will be accessible by JWT with cached policies")
                self.authorization_type = aws_apigateway.AuthorizationType.CUSTOM
                # we have to define our custom Authorizers
                for size in SIZE:
                    authorizer_clean_name = f"py-authorizer_lambda"
                    authorizer_name = f"{authorizer_clean_name}-{size.value}-{construct_id}"
                    self.authorizers[size] = aws_apigateway.RequestAuthorizer(
                        self, f"authorizer{authorizer_name}",
                        identity_sources=[aws_apigateway.IdentitySource.header("Authorization")],
                        authorizer_name=f"{authorizer_name}-{construct_id}",
                        # this Authorizer responses will be cached
                        # NOTE that this cache policy for 5 minutes can be too long from security perspective
                        results_cache_ttl=Duration.minutes(5),
                        handler=aws_lambda.Function(
                            self, f"lambda{authorizer_name}",
                            function_name=f"{authorizer_name}",
                            runtime=RUNTIME.PYTHON.value,
                            handler=HANDLER.PYTHON.value,
                            memory_size=size.value,
                            timeout=Duration.seconds(10),
                            architecture=aws_lambda.Architecture.ARM_64,
                            code=aws_lambda.Code.from_asset(
                                str(lambda_packages_location / f"{authorizer_clean_name}-deployment-package.zip"),
                            ),
                            application_log_level="INFO",
                            log_format="JSON",
                            system_log_level="INFO",
                            log_group=lambdas_log_group,
                            environment={ 
                                #! jwksResponse env variable will have "simulated JWKS response" including kid and public key
                                #! DO NOT USE THIS PATTERN IN REAL API! Call jwks endpoint of your IdP
                                "jwksResponse": simulated_jwks_response,
                            },
                        )
                    )
            case _:
                raise ValueError(f"Unknown access type {self.access}")
    
        #------------------------------------------------------------------------------
        # S3 bucket
        # NOTE that we create a bucket per API
        bucket_name = f"bckt-apitest-{self.access.value.lower()}-{construct_id.lower()}"
        self.s3_bucket_construct = aws_s3.Bucket(
            self, bucket_name,
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            bucket_name=bucket_name,
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
        )
        #------------------------------------------------------------------------------

        self.lambda_codes:Dict[LANG, Dict[str, aws_lambda.Code]] = {}
        self.lambda_constructs:Dict[str, Dict[str, aws_lambda.Function]] = {}

        #------------------------------------------------------------------------------
        # next we define the REST API on API Gateway
        self.api_construct = aws_apigateway.RestApi(
            self, f"restapi-{construct_id}",
            rest_api_name=f"restapi-{construct_id}",
            description=f"API for testing {construct_id} application",
            retain_deployments=False,
            endpoint_types=[aws_apigateway.EndpointType.REGIONAL],
            # default_method_options=aws_apigateway.MethodOptions(
            #     authorization_type=self.authorization_type,),
            deploy_options=aws_apigateway.StageOptions(
                stage_name="api",
                logging_level=aws_apigateway.MethodLoggingLevel.INFO,
                access_log_destination=aws_apigateway.LogGroupLogDestination(api_execution_log_group),
                data_trace_enabled=False,
                metrics_enabled=False,
                tracing_enabled=False,
                variables={
                    "testBucketName": self.s3_bucket_construct.bucket_name,
                    "jwtAudience": 'ApiGwLatencyTestAudience',
                    "jwtIssuer": 'https://ApiGwLatencyTestIssuer',
                    "jwksUrl": 'https://testIssuer/jwks.json',
                },
            ),
        )
        # we need to add IAM Role permission to invoke the API if ACCESS.IAM
        if self.access == ACCESS.IAM:
            self.iam_invocation_role.add_to_policy(aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                resources=[self.api_construct.arn_for_execute_api()],
                actions=["execute-api:Invoke"],
            ))
        #------------------------------------------------------------------------------
        # we need to add mock endpoints and as it's universal we'll add one per each size to cover authorizers
        mock_resource = self.api_construct.root.add_resource("mock")
        for size in SIZE:
            mock_resource.add_resource(f"mock-{size.value}").add_method(
                "GET",
                aws_apigateway.MockIntegration(
                    integration_responses=[ aws_apigateway.IntegrationResponse(status_code="200") ],
                    passthrough_behavior=aws_apigateway.PassthroughBehavior.NEVER,
                    request_templates={ "application/json": '{ "statusCode": 200 }' }
                ),
                method_responses=[aws_apigateway.MethodResponse(status_code="200")],
                authorization_type=self.authorization_type,
                authorizer=self.authorizers[size] if self.authorization_type==aws_apigateway.AuthorizationType.CUSTOM else None,
                operation_name="mocked-get",
            )
        # and now the fancy stuff - we'll generate Lambdas and add resources to our API
        # all as part of set of nested loops
        lang_resources:Dict[LANG, aws_apigateway.Resource] = {}
        for lambda_package in lambda_packages_location.glob("*-deployment-package.zip"):
            if lambda_package.is_dir() or "authorizer" in lambda_package.stem:
                # we skip all folder and authorizer deployment packages
                continue
            # now we need to handle package name according to naming convention
            clean_name = lambda_package.stem.replace("-deployment-package","")
            lang_prefix = clean_name.split("-")[0]
            try:
                lambda_lang = LANG.byValue(lang_prefix)
                lambda_runtime = RUNTIME[lambda_lang.name]
            except Exception as e:
                _top_logger.warning(f"Failed to create Code/runtime for {lambda_lang.name}")
            if lambda_lang not in lang_resources:
                lang_resources[lambda_lang] = self.api_construct.root.add_resource(lambda_lang.value)
            self.lambda_codes.setdefault(lambda_lang, {})
            self.lambda_constructs.setdefault(lambda_lang.name, {})

            if clean_name not in self.lambda_codes[lambda_lang]:
                lambda_code = aws_lambda.Code.from_asset(str(lambda_package))
                self.lambda_codes[lambda_lang][clean_name] = lambda_code
            else:
                lambda_code = self.lambda_codes[lambda_lang][clean_name]

            # Now we can define number of constructs for each required size
            # we'll also create resources with GET methods wired to each Lambda
            for size in SIZE:
                base_function_name = f"{clean_name}-{size.value}"
                final_resource = lang_resources[lambda_lang].add_resource(base_function_name.replace("_", ""))
                function_name = f"{base_function_name}-{construct_id}"
                if function_name not in self.lambda_constructs[lambda_lang.name]:
                    lambda_function = aws_lambda.Function(
                        scope=self, id=function_name,
                        function_name=function_name,
                        description=str(lambda_package.stem),
                        architecture=aws_lambda.Architecture.ARM_64,
                        memory_size=size.value,
                        runtime=lambda_runtime.value,
                        handler=HANDLER[lambda_lang.name].value,
                        code=lambda_code,
                        application_log_level="INFO",
                        log_format="JSON",
                        system_log_level="INFO",
                        log_group=lambdas_log_group,
                        # log_retention=aws_logs.RetentionDays.ONE_DAY, # this was moved moved to LogGroup feature !!!
                        timeout=Duration.seconds(29), # 29 is a max for API GW
                        retry_attempts=0
                    )
                    self.lambda_constructs[lambda_lang.name][function_name] = lambda_function
                else:
                    lambda_function = self.lambda_constructs[lambda_lang.name][function_name]
                # allow operation on S3 bucket
                if ("authorizer" not in function_name) and ("action" in function_name):
                    self.s3_bucket_construct.grant_read_write(lambda_function)
                    self.s3_bucket_construct.grant_delete(lambda_function)
                
                final_resource.add_method("GET",
                    aws_apigateway.LambdaIntegration(lambda_function),
                    authorization_type=self.authorization_type,
                    authorizer=self.authorizers[size] if self.authorization_type==aws_apigateway.AuthorizationType.CUSTOM else None,
                    operation_name=f"{function_name}-get",
                )
                _top_logger.info(f"Completed for {self.access.value}/{lambda_lang.value}/{function_name}/{size.value} Lambda Function construct")