'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from __future__ import annotations
from typing import List, Dict, Union
from queue import Queue
from enum import Enum
from .common import clean_name
from .request import TestRequest, TestRequestAuthType
import boto3
import time
from uuid import uuid4
import json
import logging
_top_logger = logging.getLogger(__name__)


class TaskType(Enum):
    ''' supported task types. Values to be used in Test Template and Plan json'''
    REQUEST = "request"
    WAIT_MIN = "wait_min"
    WAIT_SEC = "wait_sec"
    WAIT_MSEC = "wait_msec"

    @staticmethod
    def byValue(value:str) -> TaskType:
        for lang in TaskType:
            if lang.value == value:
                return lang
        raise ValueError(f"Unknown TaskType value '{value}'")

class Task:
    ''' parent class for all types of tasks '''
    name:str
    definition:Union[Dict, List, str, int, float]
    result_queue:Queue
    error_queue:Queue

    def __init__(self, 
                 task_name:str, task_definition:dict, 
                 result_queue:Queue, error_queue:Queue):
        ''' '''
        self.name = task_name
        self.definition = task_definition
        self.result_queue = result_queue
        self.error_queue = error_queue

    def execute(self, dry_run:bool, options:Union[Dict, None]=None):
        ''' '''

class TaskWait(Task):
    ''' '''
    def execute(self, dry_run:bool, options:Union[Dict, None]=None):
        ''' '''
        if dry_run:
            return
        if isinstance(self.definition, (int, float)):
            if self.name.endswith("msec"):
                time.sleep(self.definition/1000)
            elif self.name.endswith("sec"):
                time.sleep(self.definition)
            elif self.name.endswith("min"):
                time.sleep(self.definition*60)
            else:
                self.error_queue.put(f"Unknown wait type {self.name}")
        else:
            self.error_queue.put(f"Wait Task should have just a numeric value but has {self.definition}")

class TaskRequest(Task):
    ''' '''
    aws_credentials:Union[Dict[str, Union[str, None]],None] = None

    def execute(self, dry_run:bool=False, options:Union[Dict, None]=None):
        ''' '''
        if isinstance(self.definition, dict):
            request = TestRequest()
            # we need to identify what is desired authentication for this request
            request_auth = self.definition.get("auth", "") or ""
            match request_auth:
                case "IAM":
                    # IAM authentication requested
                    if TaskRequest.aws_credentials is None:
                        with open("cloud_config.json", "r") as f:
                            cloud_config = json.load(f)
                        # we'll assume predefined role
                        sts_client = boto3.client('sts')
                        assume_role_resp = sts_client.assume_role(
                            RoleArn=cloud_config["ApiTestRoleStack"]["ApiInvocationRoleArn"],
                            RoleSessionName=str(uuid4()),
                            DurationSeconds=10*60*60 # 10 hours for running test without reassuming the role (mak 12 per Role definition)
                        )
                        aws_creds = assume_role_resp["Credentials"]
                        TaskRequest.aws_credentials = {
                            "access_key_id": aws_creds["AccessKeyId"],
                            "secret_access_key": aws_creds["SecretAccessKey"],
                            "session_token": aws_creds["SessionToken"]
                        }
                    request.auth_creds = { 
                        **{ "auth_type": TestRequestAuthType.AWS_ASSUME },
                        **TaskRequest.aws_credentials
                    }
                case "":
                    # we don't have any auth
                    # in our pattern this means do nothing
                    pass
                case _:
                    # we have a token!
                    request.auth_creds = {
                        "auth_type": TestRequestAuthType.JWT,
                        "BEARER": request_auth
                    }
            # now we're ready to place a request
            try:
                req_result = request.place(
                    url=self.definition["uri"], #! NOTE that uri supports format of <scheme>://<netloc>/<path>?<query>#<fragment>
                    method=self.definition.get("method", "GET"),
                    headers=self.definition.get("headers", {}),
                    body=self.definition.get("body", None),
                    dry_run=dry_run,
                )
                if isinstance(req_result,dict) and req_result.get("statusCode",None) == 200:
                    self.result_queue.put_nowait({**req_result, **{"task": self.name}})
                else:
                    self.error_queue.put_nowait({**req_result, **{"task": self.name}})

            except Exception as e:
                message = f"Fail to execute request to URI {self.definition.get('uri','UNKNOWN')} with exception {e}"
                _top_logger.error(message)
                self.error_queue.put_nowait({"message": message, "task": self.name})
        else:
            message = f"Request Task should have a dictionary as a definition but has {self.definition}"
            _top_logger.error(message)
            self.error_queue.put_nowait({"message": message, "task": self.name})



class TaskFactory:
    ''' task factory for all supported tasks '''

    _TASKS_BY_TYPES:dict = {
            TaskType.REQUEST: TaskRequest,
            TaskType.WAIT_MIN: TaskWait,
            TaskType.WAIT_SEC: TaskWait,
            TaskType.WAIT_MSEC: TaskWait,
        }
    
    def __init__(self):
        ''' '''
        _top_logger.debug(f"TaskFactory initialized with {len(self._TASKS_BY_TYPES)} task types")
        _top_logger.debug(f"TaskFactory initialized with {self._TASKS_BY_TYPES}")

    def create(self, task_type:str, task_name:str, task_definition:dict,
               result_queue:Queue, error_queue:Queue) -> Task:
        ''' '''
        task_type = clean_name(task_type)
        if task_type in TaskType:
            task_class = self._TASKS_BY_TYPES[TaskType.byValue(task_type)]
            return task_class(task_name, task_definition, result_queue, error_queue)
        else:
            raise Exception(f"Unknown task type {task_type}")

