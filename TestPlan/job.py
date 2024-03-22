'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from .task import Task, TaskFactory, TaskType
from typing import List, Dict, Union
from dataclasses import dataclass
from queue import Queue
from .common import clean_name
import logging
_top_logger = logging.getLogger(__name__)

@dataclass
class JobExecuteOptions:
    ''' '''
    results_queue:Queue
    errors_queue:Queue

class Job:
    ''' '''
    name:str = ""
    definition:dict = {}
    tasks:Dict[str, Task] = {}
    options:JobExecuteOptions

    def __init__(self, job_name:str, job_definition:dict, job_options:JobExecuteOptions):
        ''' '''
        self.name = job_name
        self.definition = {clean_name(task_name):v for task_name,v in job_definition.items()}
        self.options:JobExecuteOptions = job_options
        # we need to create underlying Tasks first
        task_factory = TaskFactory()

        self.tasks = {task_name:task_factory.create(
                            task_type=task_def.get("TASK_TYPE", task_name) if isinstance(task_def, dict) else task_name,
                            task_name=task_name, task_definition=task_def, 
                            result_queue=self.options.results_queue,
                            error_queue=self.options.errors_queue) 
                        for task_name,task_def in self.definition.get("tasks", {}).items()}

    def execute(self, dry_run:bool=False):
        ''' '''
        # we'll just execute Tasks one-by-one
        for task_name,task in self.tasks.items():
            _top_logger.debug(f"Executing task {task_name}")
            try:
                task.execute(dry_run=dry_run)
            except Exception as e:
                message = f"FAIL to execute task {self.name} with exception {e}"
                _top_logger.error(message)
                self.options.errors_queue.put_nowait({"message": message, "task": task_name})
            _top_logger.debug(f"Task {task_name} completed")
