'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from typing import Dict
import sys
from pathlib import Path
import argparse
from uuid import uuid4
import datetime
import os
import subprocess
import shutil
import json
import jwt as PyJWT
#-------------------------
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))


def parse_arguments():
    '''  '''
    parser = argparse.ArgumentParser(
        description="Generate key pair and JWTs to be used by protected endpoint instead of real IdP communications",
        usage=''' python3 gen_keys.py'''
    )
    parser.add_argument("--algorithm", "-alg", dest="alg", required=False, default="RS256", help="JWT signing algorithm")
    parser.add_argument("--key_id", "-kid", dest="kid", required=False, default=None, help="JWT key id")
    parser.add_argument("--issuer", "-iss", dest="iss", required=False, default="https://ApiGwLatencyTestIssuer", help="JWT issuer. MUST be the same as defined in the AppStack!")
    parser.add_argument("--audience", "-aud", dest="aud", required=False, default="ApiGwLatencyTestAudience", help="JWT audience. MUST be the same as defined in the AppStack!")
    parser.add_argument("--jwks_dest", "-jwks", dest="jwks_dest", required=False, default="jwks_response.json", help="Where to store generated public key in jwks format")
    parser.add_argument("--private_pem", "-pem", dest="pem_dest", required=False, default="private_key.json", help="Where to store generated private key in PEM-like format")
    parser.add_argument("--jwts_dest", "-jwts", dest="jwts_dest", required=False, default="test_jwts.json", help="Where to store generated JWTs")

    args = parser.parse_args()
    return args


if __name__=="__main__":

    # parse and collect command line arguments
    my_args = parse_arguments()
    _top_logger.debug(my_args)

    new_kid = my_args.kid or str(uuid4())
    new_alg = my_args.alg
    new_jwks_dest = Path(my_args.jwks_dest)
    new_pem_dest = Path(my_args.pem_dest)
    new_jwts_dest = Path(my_args.jwts_dest)
    new_issuer = my_args.iss
    new_audience = my_args.aud
    
    work_folder = Path("GenRSA")
    # invoke gen_keys.py
    curr_path = os.getcwd()
    os.chdir(work_folder)
    # remove venv if there
    shutil.rmtree(work_folder / ".venv", ignore_errors=True)
    command_line = f"python3 -m venv .venv; source .venv/bin/activate; pip install -r requirements.txt; python gen_keys.py -alg '{new_alg}' -kid '{new_kid}' -jwks temp_jwks.json -pem temp_pem.json"
    # *NOTE* blocking check_call is used as process is typically fast running
    subprocess.check_call(command_line, shell=True)
    os.chdir(curr_path)
    # now we just need to move created files to route and remove created .venv in the work folder
    shutil.move(work_folder / "temp_jwks.json", new_jwks_dest)
    shutil.move(work_folder / "temp_pem.json", new_pem_dest)
    shutil.rmtree(work_folder / ".venv", ignore_errors=True)

    # keys generated, stored in files and ready to be used by other components
    _top_logger.info(f"Keys generated and stored for use in {new_jwks_dest} and {new_pem_dest}")
    _top_logger.info("NOTE that you'll HAVE TO RERUN 'python deploy' after keys generation!!!")

    # last but not least - we need couple of JWTs to use it with our tests
    # load private key first
    with open(new_pem_dest, "r") as f:
        private_key_info = json.load(f)
    _top_logger.info("Generating couple of JWTs to test with")
    tokens:Dict[str,str] = {}
    for i in ["ApiTestJwt", "ApiTestJwtcached"]:
        _top_logger.info(f"JWT for {i}")
        tokens[i] = PyJWT.encode(
             payload={
                "iss": new_issuer,
                "aud": new_audience,
                "iat": datetime.datetime.now(),
                "exp": (datetime.datetime.now() + datetime.timedelta(days=365)), # test token will be valid for YEAR !
                "nbf": datetime.datetime.now(),
            },
            headers={"alg": new_alg, "kid": new_kid},
            key=private_key_info["pem"],
            algorithm=new_alg
        )
    with open(new_jwts_dest, "w") as f:
        json.dump(tokens, f, indent=2)