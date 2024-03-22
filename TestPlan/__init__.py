'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from .reporter import Reporter
from .stage import Stage
from typing import List, Dict, Union
import logging

_top_logger = logging.getLogger(__name__)


class TestPlan:
    ''' Create and execute the Test Plan'''
    name:str = ""
    stages:Dict[str, Stage] = {}    # key - stage name
    pool_size:int = 0

    def __init__(self, plan_name:str, plan_definition:dict, reporter:Reporter, max_concurrency:int=10):
        self.name = plan_name
        # we need to create underlying Jobs first
        self.stages = {
            k: Stage(k, v, reporter, max_concurrency) 
                for k,v in plan_definition.get("stages",{}).items()
                    # if we want to sort the stages we need to:
                    # dict(
                    #     sorted(
                    #         plan_definition.get("stages",{}).items(),
                    #         key=lambda stageDef: f'{int(stageDef[0].split("_")[0]):05}' #if stageName[0].split("_")[0].isnumeric() else stageName
                    #     )
                    # ).items()
        }
        self.pool_size = max_concurrency

    def execute(self, dry_run:bool=False, options:Union[Dict, None]=None):
        ''' execute all Stages sequentially '''

        for stage_name, stage in self.stages.items():
            _top_logger.info(f"Will execute the stage {stage_name}")
            stage.execute(dry_run=dry_run)

