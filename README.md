# General statement
This repo contains infrastructure and testing code for Lambda-backed REST API performance analysis.

See details in the article [Performance analysis of Lambda-backed REST API on the AWS API Gateway for Python, Go and TypeScript](https://daniil-sokolov.medium.com/performance-analysis-of-lambda-backed-rest-api-on-the-aws-api-gateway-for-python-go-and-typescript-bc296732e5ae)on the medium.com

Please note that this is not a "production ready" code - it's more a starting point for anyone interested in testing REST API

# Usage
You'll need AWS account and AWS CDK installed/configured to deploy the infrastructure. You'll also need to bootstrap your account/region with `cdk bootstrap`

## To deploy the infrastructure:
- create (Mac: `python3 -m venv .venv`) and activate (Mac: `source .venv/bin/activate`) venv
- install dependencies in the venv (Mac: `pip install -r requirements.txt`)
- prepare deployment packages for all Lambdas by running build_lambdas.py (`python build_lambdas.py`)
    - you'll need go 1.20+ installed ([here](https://go.dev/dl/))
        - additional details on Go Lambdas can be found [here](https://aws.github.io/aws-sdk-go-v2/docs/getting-started/), [here](https://docs.aws.amazon.com/lambda/latest/dg/lambda-golang.html) and [here](https://github.com/aws/aws-lambda-go/blob/main/events/README_ApiGatewayEvent.md)
    - this step is separated so you'll be able to run build/packaging separately. But it's not needed if you'll use `deploy.py` (described below) as it'll call `build_lambdas.py` anyway
- run `python gen_tokens.py` if deploying first time or want to rotate keys. This will create key-pair for JWT protected APIs
    - you can find other gen_keys.py options by running `python gen_tokens.py --help`
    - __NOTE__ this will create and store keys locally (private) and in the environment variable (public). __NEVER DO THAT IN YOUR REAL APIs__ This is unsecure anti-pattern. Here we're doing that as we are just "simulating" real authentication/authorization
    - __NOTE__ you'll need to redeploy infrastructure with `python deploy.py` after regenerating tokens/keys !!!
- run `python deploy.py` to deploy infrastructure with your default AWS profile
    - you can find other deploy.py options by running `python deploy.py --help`
    - __NOTE__ with this large infrastructure deployment process (even with minor changes) will have tens of minutes!
    - alternatively you can run `cdk deploy --all --require-approval never --outputs-file cloud_config.json` to deploy but you'll need to update the template manually
        - __NOTE__ that you need to add `--all` as our infrastructure consists of multiple stacks
        - __NOTE__ that you need to use `--outputs-file cloud_config.json` to collect information about deployed APIs URLs
        - __NOTE__ that if you'll change output file you'll have to change the template!

## To prepare the Test Plan but not executing it:
- run `python load_latency.py --dry`
    - you can find other load_latency.py options by running `python load_latency.py --help`
    - default test plan is available in templates/load_test.json.jinja

# Test Plan Template
- see default template for comments on structure and parameters details
- NOTE that templates are transformed into executable plan in two steps:
    - template is expanded with jinja
        - On this step jinja syntax is transformed into JSON file
        - Mostly this step is used to expand jinja loops, ifs, variables, etc
        - resulting JSON still has "VARIABLES" which can be referenced in jinja syntax
        - result of this step is stored in the root folder under template name but w/o 'jinja' extension
    - template is finally prepared and cleaned
        - VARIABLES are used to fill values in the template
            - in addition to standard jinja variables syntax `{file}://<path>-><key>{file_end}` can be used for variable value. It's expected that file is json with keys on the top level. NOTE that exact `{file}://` prefix will trigger collection of value from the file.
        - comments removed
        - result of this step is stored in the root folder under template name but with 'FINAL' affix

# Run Test
Please note that test plan execution may
- **take a long time (up to hours)**
- **can result in considerable cloud cost!**

To run the test just execute `python load_latency.py` and wait for results available in the "output file"