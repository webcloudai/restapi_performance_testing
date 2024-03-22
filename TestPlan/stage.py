'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from .reporter import Reporter, LogRecord, LogRecordType
from .job import Job, JobExecuteOptions
from queue import Queue
from typing import List, Dict, Union
from concurrent.futures import ThreadPoolExecutor
from .common import clean_name
import logging
import time
_top_logger = logging.getLogger(__name__)

class Stage:
    ''' '''
    jobs:Dict[str, Job] = {}    # key - job name
    result_queues:Dict[str, Queue] = {} # key - job name
    error_queues:Dict[str, Queue] = {}  #key - job name
    pool_size:int = 10
    name:str = ""
    definition:dict = {}

    def __init__(self, stage_name:str, stage_definition:dict, reporter:Reporter, max_concurrency:int=3):
        ''' '''
        self.reporter:Reporter = reporter
        self.name = stage_name
        self.definition = {clean_name(k):v for k,v in stage_definition.items()}
        # we need to create underlying Queues and Jobs first
        self.result_queues = {job_name:Queue() for job_name in self.definition.get("jobs",{}).keys()}
        self.error_queues = {job_name:Queue() for job_name in self.definition.get("jobs",{}).keys()}
        self.jobs = {job_name:Job(job_name, job_def, JobExecuteOptions(
                                    results_queue=self.result_queues[job_name],
                                    errors_queue=self.error_queues[job_name]
                                )) 
                    for job_name,job_def in self.definition.get("jobs",{}).items()}
        # we'll run start all jobs in parallel Threads with Pool size of max_concurrency at max
        self.pool_size = min(max_concurrency, len(self.jobs))

    def execute(self, dry_run:bool=False, options:Union[Dict, None]=None):
        ''' execute all underlying jobs in parallel '''
       
        # we'll listen for messages in all queues
        # we'll start all jobs in parallel Threads with Pool size of self.pool_size at max
        thread_pool = ThreadPoolExecutor(max_workers=self.pool_size)
        jobs_submitted = {
            job_name: thread_pool.submit(job.execute, dry_run=dry_run)
            for job_name, job in self.jobs.items()
        }
        # now we'll listen for messages in all result and error queues
        jobs_running = True
        have_message = False
        while jobs_running or have_message:
            jobs_running = False
            have_message = False
            time.sleep(0.5)
            for job_name, job in jobs_submitted.items():
                jobs_running = jobs_running or not job.done()
                try:
                    result_message = self.result_queues[job_name].get_nowait()
                    have_message = True
                    # we have a result available in this Queue
                    # we'll assemble a record and send it to the Reporter
                    _top_logger.info(f"Got a message in the results queue {result_message}")
                    self.reporter.add(
                        LogRecord(
                            stage=self.name,
                            job=job_name,
                            task=result_message.get("task","NA") if isinstance(result_message, dict) else "NIM",
                            logType=LogRecordType.LATENCY,
                            data=result_message
                        )
                    )
                except Exception as e:
                    # no result available in this Queue
                    pass

                try:
                    err_message = self.error_queues[job_name].get_nowait()
                    have_message = True
                    _top_logger.info(f"Got a message in the errors queue {err_message}")
                    self.reporter.add(
                        LogRecord(
                            stage=self.name,
                            job=job_name,
                            task=err_message.get("task","NA") if isinstance(err_message, dict) else "NIM",
                            logType=LogRecordType.ERROR,
                            data=err_message
                        )
                    )
                except Exception as e:
                    # no errors available in this Queue
                    # we have an error available in this Queue
                    # we'll assemble a record and send it to the Reporter
                    pass
                
        if not jobs_running and not have_message:
            _top_logger.info(f"No messages in any of the queues for stage {self.name}")

        # # we'll wait for all jobs to finish
        # print(f"Waiting for all jobs to finish", end="")
        # for job in jobs_submitted.values():
        #     while not job.done():
        #         print(".", end="")
        #         time.sleep(0.5)
        print(f"All {len(jobs_submitted)} jobs of stage {self.name} COMPLETED")



