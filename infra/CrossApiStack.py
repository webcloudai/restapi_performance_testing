'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from __future__ import annotations
from aws_cdk import (
    Stack,
    aws_iam,
    CfnOutput,
    Duration
)
from constructs import Construct
import logging
_top_logger = logging.getLogger(__name__)


class ApiInvocationRoleStack(Stack):

    def __init__(
            self, scope: Construct, construct_id: str,
            api_invocation_role_name:str,
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # definition: sfn.IChainable
        self.role = aws_iam.Role(self, "Role",
            assumed_by=aws_iam.AccountPrincipal(self.account), # aws_iam.AnyPrincipal()
            role_name=api_invocation_role_name,
            description="Role to be assumed by ApiGwTest",
            max_session_duration=Duration.hours(12),
        )
        CfnOutput(
            self,
            f"ApiInvocationRoleArn",
            value=self.role.role_arn,
            export_name="ApiInvocationRoleArn"
        )
        CfnOutput(
            self,
            f"ApiInvocationRoleName",
            value=self.role.role_name,
            export_name="ApiInvocationRoleName"
        )