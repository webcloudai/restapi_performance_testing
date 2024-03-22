import aws_cdk as cdk
import aws_cdk.assertions as assertions
from infra.CrossApiStack import ApiInvocationRoleStack
from infra.ApplicationStack import ApplicationStack, ACCESS

def simplest_possible_basic_test():
    app = cdk.App()
    role_name = f"UT_ApiTestRole"
    invocationRoleStack = ApiInvocationRoleStack(
        app, f"UT_ApiTestRoleStack",
        api_invocation_role_name=role_name
    )
    stack = ApplicationStack(
        app, "UT_aws-apigw-performance-testing",
        access_type=ACCESS.IAM,
        iam_invocation_role=invocationRoleStack.role,
        simulated_jwks_response="",
    )
    template = assertions.Template.from_stack(stack)

