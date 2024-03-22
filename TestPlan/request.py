'''
© 2024 Daniil Sokolov <{$contact}>
MIT License
'''
import requests
from urllib3.util.retry import Retry
from urllib.parse import urlsplit
from requests.adapters import HTTPAdapter
import json
import uuid
from enum import Enum
import datetime, hashlib, hmac
from typing import Union
from time import perf_counter
import jwt
import logging
_top_logger = logging.getLogger(__name__)

class TestRequestAuthType(Enum):
    ''' available authentication types (value identifies the list of dict keys) '''
    AWS_ASSUME = ("access_key_id","secret_access_key","session_token")
    JWT = (
        "BEARER",      # if provided all other properties are ignored
        "private_key", # for RS256 expected to be something like b"-----BEGIN PRIVATE KEY-----\nABCDE..."
        "alg",   # will be RS256 if not provided
        "kid",   # optional! claim
        "aud","iss", # these two claims are REQUIRED!
        "iat", "exp", "nbf"  # will be filled with now() and horrible now()+12h if not provided
        # claims not controlled for now: "sub", "jti", "azp", "scope", "gty"
    )
        

def create_bearer(jwt_options_and_claims:dict)->str:
    ''' create bearer token from claims '''
    p_key = jwt_options_and_claims["private_key"]
    alg = jwt_options_and_claims.get("alg", "RS256")
    kid = jwt_options_and_claims.get("kid", None)
    # claims supported by pyJWT per https://pyjwt.readthedocs.io/en/latest/usage.html#registered-claim-names
    claims_and_opts = {
        "iss": "Issuer",            #! REQUIRED
        "aud": "Audience",          #! REQUIRED
        "iat": "Issued At",         # will be now() if not provided
        "exp": "Expiration Time",   # will be horrible 12h if not provided
        "nbf": "Not Before Time",   # will be now() if not provided
        "private_key": None, "alg": None, "kid": None # options, not a claims
    }
    signed_jwt:str = jwt.encode(
        payload={
            **{
                "iss": jwt_options_and_claims["iss"],
                "aud": jwt_options_and_claims["aud"],
                "iat": jwt_options_and_claims.get("iat", None) or datetime.datetime.now(), #tz=timezone.utc)
                "exp": jwt_options_and_claims.get("exp", None) or (datetime.datetime.now() + datetime.timedelta(hours=12)),
                "nbf": jwt_options_and_claims.get("nbf", None) or datetime.datetime.now(),
            },
            **{k:v for k,v in jwt_options_and_claims.items() if k not in claims_and_opts}
        },
        key=p_key,
        algorithm=alg,
        headers={"kid": kid} if isinstance(kid, str) else None,
    )
    return signed_jwt

class TestRequest():

    def __init__(self, *,
                region="us-east-1",
                retries=0,
                backoff_factor=0.3,
                force_list = None ): # [500, 502, 503, 504] ):
        ''' creates request session with common parameters '''
        self._logger = logging.getLogger(__name__)
        self._region = region
        self._request_id = None
        self._request:Union[requests.Request,None] = None
        self._response:Union[requests.Response,None] = None
        self._auth = None
        self._session = requests.Session()
        if isinstance(force_list, list):
            retry = Retry(
                total=retries,
                read=retries,
                connect=retries,
                backoff_factor=backoff_factor,
                status_forcelist=force_list)
        else:
            retry = None
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    @property
    def auth_creds(self):
        return self._auth
    @auth_creds.setter
    def auth_creds(self, value:dict):
        ''' fill in credentials depending from authentication type '''
        _auth = {}
        try:
            # verified that parameters were provided and copy them
            if value["auth_type"] in TestRequestAuthType:
                _auth["auth_type"] = value["auth_type"]
                for k in value["auth_type"].value:
                    _auth[k] = value.get(k, None)
            else:
                self._logger.error(f"Auth type {value['auth_type']} is not supported for now")
                raise ValueError
        except Exception as e:
            self._logger.error(f"Fail to handle authentication parameters")
            self._logger.error(e)
            raise e
        self._auth = _auth

    def _sign(self)->Union[str, None]:
        ''' sign provided object '''

        # Key derivation functions. See:
        # http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        def getSignatureKey(key, dateStamp, regionName, serviceName):
            kDate = sign(("AWS4" + key).encode("utf-8"), dateStamp)
            kRegion = sign(kDate, regionName)
            kService = sign(kRegion, serviceName)
            kSigning = sign(kService, "aws4_request")
            return kSigning
        
        if not isinstance(self._auth, dict):
            self._logger.error(f"Auth parameters are not provided")
            raise ValueError(f"Auth parameters are not provided")

        if self._auth["auth_type"] == TestRequestAuthType.AWS_ASSUME:
            # AWS IAM AUTHENTICATION

            # service identifiers auth scope
            service = "execute-api"

            # Create a date for headers and the credential string
            now_utc = datetime.datetime.utcnow()
            amzdate = now_utc.strftime("%Y%m%dT%H%M%SZ")
            datestamp = now_utc.strftime("%Y%m%d") # Date w/o time, used in credential scope

            # Step 2: Create canonical URI--the part of the URI from domain to query 
            # string (use '/' if no path)
            canonical_uri = self._url.path if len(self._url.path)>0 else "/" 

            # Step 3: Create the canonical query string. In this example (a GET request),
            # request parameters are in the query string. Query string values must
            # be URL-encoded (space=%20). The parameters must be sorted by name.
            # For this example, the query string is pre-formatted in the request_parameters variable.
            if len(self._url.query.split("&")) > 1:
                canonical_querystring = "&".join(sorted(self._url.query.split("&")))
            else:
                canonical_querystring = self._url.query
            # Step 4: Create the canonical headers and signed headers. Header names
            # must be trimmed and lowercase, and sorted in code point order from
            # low to high. Note that there is a trailing \n.
            self._headers["host"] = self._url.hostname
            self._headers["x-amz-date"] = amzdate
            self._headers["x-amz-security-token"] = self._auth["session_token"]
            self._headers = {k.lower():v for k,v in self._headers.items()}

            canonical_names = sorted(list(self._headers.keys()))
            canonical_headers = ""
            for h_name in canonical_names:
                canonical_headers += f"{h_name}:{self._headers[h_name]}\n"
                
            # Step 5: Create the list of signed headers. This lists the headers
            # in the canonical_headers list, delimited with ";" and in alpha order.
            # Note: The request can include any headers; canonical_headers and
            # signed_headers lists those that you want to be included in the 
            # hash of the request. "Host" and "x-amz-date" are always required.
            signed_headers = f"{';'.join(canonical_names)}"
            #signed_headers = f"host;x-amz-date;X-Amz-Security-Token;{';'.join(self._headers.keys())}"

            # Step 6: Create payload hash (hash of the request body content). For GET
            # requests, the payload is an empty string ("").
            payload_hash = hashlib.sha256(self._body.encode("utf-8")).hexdigest()

            # Step 7: Combine elements to create canonical request
            canonical_request = f"{self._method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
            
            # ************* TASK 2: CREATE THE STRING TO SIGN*************
            # Match the algorithm to the hashing algorithm you use, either SHA-1 or
            # SHA-256 (recommended)
            algorithm = "AWS4-HMAC-SHA256"
            credential_scope = f"{datestamp}/{self._region}/{service}/aws4_request"
            string_to_sign = f"{algorithm}\n{amzdate}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
            
            # ************* TASK 3: CALCULATE THE SIGNATURE *************
            # Create the signing key using the function defined above.
            signing_key = getSignatureKey(self._auth["secret_access_key"], datestamp, self._region, service)

            # Sign the string_to_sign using the signing_key
            signature = hmac.new(signing_key, (string_to_sign).encode('utf-8'), hashlib.sha256).hexdigest()

            # ************* TASK 4: ADD SIGNING INFORMATION TO THE REQUEST *************
            # Put the signature information in a header named Authorization.
            authorization_header = f"{algorithm} Credential={self._auth['access_key_id']}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
            #self._headers.setdefault("x-amz-date", amzdate)
            self._headers.setdefault("Authorization", authorization_header)
        elif self._auth["auth_type"] == TestRequestAuthType.JWT:
            # JWT AUTHENTICATION - we need a token if _self._auth["BEARER"] is None
            if not isinstance(self._auth["BEARER"], str):
                # we need a token
                _top_logger.warning(f"Will CREATE TOKEN.")
                self._auth["BEARER"] = create_bearer(self._auth)
            self._headers.setdefault("Authorization", f"Bearer {self._auth['BEARER']}")
            return self._auth["BEARER"]

        else:
            self._logger.error(f"Auth type {self._auth['auth_type']} not supported")
            raise ValueError

    def place(self, *,
              url: str,
              method: str,
              body={},
              headers={},
              dry_run:bool=False):
        ''' method to place a call to API on the AWS APIGW
            NOTE url supports format of <scheme>://<netloc>/<path>?<query>#<fragment>
            will add headers to the request (if not provided in argument dict)
            "X-Correlation-ID" = newly generated uuid
            "Accept" =  "application/json;charset=UTF-8,version~latest",
            "Content-Type" = "application/json,charset=UTF-8"
            returns the full response dict '''
        
        self._url = urlsplit(url)
        self._body = json.dumps(body) if body and len(body)>0 else ""
        self._method = method.upper()
        self._headers = {k.lower():v for k,v in headers.items()}

        req_method = getattr(self._session, method.lower())
        if req_method is None:
            self._response = None
            logging.error(f"Incorrect http method {method}")
            raise ValueError

        # add default headers
        self._request_id = str(uuid.uuid4())
        self._headers.setdefault("X-Correlation-ID", self._request_id)
        self._headers.setdefault("Accept", "application/json")#,charset=UTF-8")
        self._headers.setdefault("Content-Type", "application/json,charset=UTF-8")
        
        # sign the request if self._auth provided
        if self._auth:
            self._sign()

        # place http request
        place_timestamp = datetime.datetime.now().timestamp()
        if dry_run:
            start_req = perf_counter()
            req = requests.Request(
                method="GET",
                url=url,
                data=self._body,
                headers=self._headers
            )
            self._response = requests.Response()
            self._response.request = req.prepare()
            self._response.status_code = 200
            # store http request as a separate property
            self._request = self._response.request
            latency = (perf_counter() - start_req) * 1000
        else:
            start_req = perf_counter()
            self._response = req_method(
                url=url,
                data=self._body,
                headers=self._headers)
            latency = (perf_counter() - start_req) * 1000
            # store http request as a separate property
            self._request = self._response.request
        # try to parse response
        try:
            response_body = json.loads(self._response.text)
        except Exception as e:
            logging.error(f"TestRequest-place: Fail to json-parse response body. Will return as is.")
            logging.debug(e)
            response_body = self._response.text
        
        return {
            "place_timestamp": place_timestamp,
            "statusCode": self._response.status_code,
            "latency": latency,
            "request_url": url,
            "request_method": method,
            "request_headers": self._headers,
            # "request_bearer": self._auth.get("BEARER", None) if isinstance(self._auth, dict) else None,
            "body": response_body,
            "headers": {k:v for k,v in self._response.headers.items()},
            # "raw_content": self._response.content
        }

    @property
    def response(self):
        return self._response

    @property
    def body(self):
        return None if self._response==None else self._response.json()

    @property
    def code(self):
        return None if self._response==None else self._response.reason

    @property
    def headers(self):
        return None if self._response==None else self._response.headers

    @property
    def ok(self):
        return None if self._response==None else self._response.ok
