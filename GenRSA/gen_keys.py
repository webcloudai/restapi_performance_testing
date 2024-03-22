'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
import sys
from pathlib import Path
import argparse
from uuid import uuid4
import json
# import jwt as PyJWT
from jwcrypto import jwk    # used for RSA key pair generation
#-------------------------
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))


def parse_arguments():
    '''  '''
    parser = argparse.ArgumentParser(
        description="Generate key pair to be used by JWT protected endpoint instead of real IdP communications",
        usage=''' python3 gen_keys.py'''
    )
    parser.add_argument("--algorithm", "-alg", dest="alg", required=False, default="RS256", help="JWT signing algorithm")
    parser.add_argument("--key_id", "-kid", dest="kid", required=False, default=None, help="JWT key id")
    parser.add_argument("--jwks_dest", "-jwks", dest="jwks_dest", required=False, default="jwks_response.json", help="Where to store generated public key in jwks format")
    parser.add_argument("--private_pem", "-pem", dest="pem_dest", required=False, default="private_key.json", help="Where to store generated private key in PEM-like format")

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
    
    '''
    from jwcrypto import jwa
    print(jwa.JWA.algorithms_registry)
    # example
    key = jwk.JWK.generate(kty='RSA', size=2048, alg='RSA-OAEP-256', use=new_kid, kid='12345')
    '''


    # full list of supported algorithms can be found in JWA.algorithms_registry
    key_pair = jwk.JWK.generate(kty='RSA', size=2048, alg=new_alg, use=new_kid, kid=new_kid)
    # we'll need public key in jwks format
    public_key:dict = key_pair.export_public(as_dict=True)
    public_key["use"] = "sig"   # weirdly enough the use value is incorrect!
    with open(new_jwks_dest, "w") as f:
        json.dump( {"keys": [ public_key ] }, f)
    
    # we'll need private key in pem format PLUS kid and alg
    private_key = key_pair.export_to_pem(private_key=True, password=None)
    private_key_pem:str = private_key.decode("utf-8")  # export private key in pem format
    with open(new_pem_dest, "w") as f:
         json.dump({
            "alg": new_alg,
            "kid": new_kid,
            "pem": private_key_pem
         }, f, indent=2)

    '''
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf8")
    with open(new_pem_dest, "w") as f:
         json.dump({
            "alg": new_alg,
            "kid": new_kid,
            "pem": private_key_pem
         }, f, indent=2)
    public_key = private_key.public_key()
    public_key_jwks = public_key.public_bytes(
         encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    '''
    # keys generated, stored in files and ready to be used by other components
    _top_logger.info(f"Keys generated and stored for use in {new_jwks_dest} and {new_pem_dest}")
    _top_logger.info("NOTE that you'll HAVE TO RERUN 'python deploy' after keys generation!!!")

