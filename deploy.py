'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
import sys
from pathlib import Path
import argparse
import subprocess
#-------------------------
import logging
import json
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger("DEPLOY")
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))


def parse_arguments():
    '''  '''
    parser = argparse.ArgumentParser(
        description="Run a cdk deployment of coded Test infrastructure",
        usage=''' python3 deploy.py'''
    )
    parser.add_argument("--skip_build", "-s", dest="skip_build", required=False, action="store_true", help="if provided will use currently available packages (will not build lambdas)")
    parser.add_argument("--config_dest", "-c", dest="config_dest", required=False, default="cloud_config.json", help="Where to store deployment info. Default = 'cloud_config.json'")
    parser.add_argument("--uris_dest", "-u", dest="uris_dest", required=False, default="test_uris.json", help="Where to store URLs of deployed APIs. Default = 'test_uris.json'")
    parser.add_argument("--deploy_stacks", "-d", dest="deploy_stacks", required=False, default="--all", help="What stacks to deploy/redeploy. Default - '--all'")

    args = parser.parse_args()
    return args

if __name__=="__main__":

    # parse and collect command line arguments
    my_args = parse_arguments()
    _top_logger.debug(my_args)
    skip_build = my_args.skip_build or False
    config_dest = Path(my_args.config_dest)
    uris_dest = Path(my_args.uris_dest)
    deploy_stacks = my_args.deploy_stacks

    if not skip_build:
         # we'll need to build all lambdas
        _top_logger.info(f"Will build and prepare packages for all Lambdas\n")
        try:
            subprocess.check_call("source .venv/bin/activate; python build_lambdas.py", shell=True)
        except Exception as e:
            _top_logger.warning(f"Failed to build lambdas with exception {e}")
            raise e
        _top_logger.info(f"All Lambdas were build and packaged for deployment\n")


    _top_logger.info(f"Will run deployment for '{deploy_stacks}' stacks\n")
    command_line = f"cdk deploy {deploy_stacks} --require-approval never --outputs-file {str(config_dest)}"

    try:
        subprocess.check_call(command_line, shell=True)
    except Exception as e:
        _top_logger.warning(f"Failed to deploy the infra with exception {e}")
        raise e

    _top_logger.info(f"Infrastructure stackS '{deploy_stacks}' deployed and ready to be used by load_latency.py")
    _top_logger.info(f"Outputs are stored in {config_dest}")

    with open(config_dest, "r") as f:
        config = json.load(f)

    # we'll now parse outputs and prepare URIs file for TEST
    uris = {}
    for k,v in config.items():
            for st_k, st_v in v.items():
                if st_k.startswith("restapi"):
                    uris[k] = st_v
                    break
    with open(uris_dest, "w") as f:
            json.dump(uris, f, indent=2)

    _top_logger.info(f"URIs are stored in {uris_dest}")
