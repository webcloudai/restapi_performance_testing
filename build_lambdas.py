'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
# helper script to build and prepare deployment for AWS Lambda when pip is used as a package manager
# NOTE: it's expected that:
# - every lambda function is located in the dedicated subfolder of src folder named exactly as Lambda function
# - requirements for all lambdas are available in lambda_requirements.txt file
#   (this may be improved with different requirements per lambda)
#
# This script is somewhat analog of this set of commands executed for every lambda
'''
rm -R build_lambda
mkdir build_lambda
rm -R deploy_lambda
mkdir deploy_lambda
cp src/* build_lambda
pip install --target ./build_lambda -r requirements.txt
cd build_lambda
zip -r ../deploy_lambda/deployment-package.zip . 
'''
import sys
import subprocess
import shutil
from pathlib import Path
import argparse
import os
#-------------------------
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger("build_lambdas")
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))

python_dependencies_list:Path = Path("lambda_requirements.txt")
ts_dependencies_list:Path = Path("package.json")

# NOTE: Current implementation do not preserve previous builds and deployments!
# create build version from datetime (if needed) - NOT SUPPORTED FOR NOW
# create current build subfolder - NOT SUPPORTED FOR NOW

def parse_arguments():
    ''' this is required ONLY if command line is used '''
    parser = argparse.ArgumentParser(
        description="Build all Lambda Functions and (optionally) run 'cdk synth' and 'cdk deploy'",
        usage=''' python3 build_lambdas.py'''
    )
    parser.add_argument("--sources_folder", "-sf", dest="sources_folder", required=False, default="./src", help="Path of the folder with Lambda sources subfolders")
    parser.add_argument("--build_folder", "-bf", dest="build_folder", required=False, default="./build_lambda", help="Path of the temp folder where Lambda build process happens")
    parser.add_argument("--deploy_folder", "-df", dest="deployment_folder", required=False, default="./deploy_lambda", help="Path of the folder with Lambda deployment packages")
    parser.add_argument("--deployment_package", "-dn", dest="deployment_package", required=False, default="lambda-deployment-package", help="common suffix for all Lambda deployment packages")

    args = parser.parse_args()
    return args



if __name__=="__main__":

    # parse and collect command line arguments
    my_args = parse_arguments()
    _top_logger.debug(my_args)

    master_sources_folder:Path = Path(my_args.sources_folder)
    build_folder:Path = Path(my_args.build_folder)
    deploy_folder:Path = Path(my_args.deployment_folder)
    deployment_package_name:Path = Path(my_args.deployment_package)

    # create build folder if needed
    # create deploy folder if needed
    for check_folder in [build_folder, deploy_folder]:
        if check_folder.is_file():
            raise RuntimeError(f"File named {check_folder} exists. Please rename or remove it!")

        if check_folder.is_dir():
            # folder exists - cleanup maybe required
            shutil.rmtree(check_folder)

        # we'll create deploy_folder as build folder will be created by copytree
        if check_folder==deploy_folder:
            Path(check_folder).mkdir(parents=True, exist_ok=True)

    # build and pack for deployment all lambda functions
    # we know that the first level of folders will be Lambda language!
    for language_folder in master_sources_folder.glob("*"):
        if not language_folder.is_dir():
            # we skip all files in the src folder as
            # every lambda language MUST be in the dedicated SUBFOLDER
            continue
        language = language_folder.parts[-1]
        for sources_folder in language_folder.glob("*"):
            if not sources_folder.is_dir():
                # we skip all files in the src folder as
                # every lambda MUST be in the dedicated SUBFOLDER
                continue
            lambda_name = sources_folder.parts[-1]
            _top_logger.info(f"Will build/package {lambda_name} for language {language}")

            work_folder = build_folder
            # check if we're building Lambda Layer (folders structure inside zip must be different!)
            # see https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html
            if lambda_name.startswith("_"):
                # TODO add support for layers in different languages
                # work_folder = build_folder / <language specific subfolder> / lambda_name
                continue
            
            # clean up build folder (just delete whole folder)
            try:
                shutil.rmtree(build_folder)
            except FileNotFoundError:
                pass
            except Exception as e:
                _top_logger.info(f"Was not able to clean up build folder with exception {e}")
                pass
            # build folder will be created automatically by copytree
            # copy ALL sources to build subfolder
            shutil.copytree(sources_folder, work_folder)
            zip_folder = build_folder
            # next step will be language-specific !
            match language:
                case "python":
                    # install dependencies to build subfolder
                    # *NOTE* if lambda subfolder will have requirements.txt it'll be used instead of global lambda_requirements.txt
                    # *NOTE* you can put empty requirements.txt into function folder if it doesn't have any dependencies
                    # it's not recommended to use ._main for pip
                    # see https://pip.pypa.io/en/latest/user_guide/#using-pip-from-your-program
                    one_lambda_dependencies = sources_folder / "requirements.txt"
                    if not one_lambda_dependencies.is_file():
                        one_lambda_dependencies = python_dependencies_list
                    if one_lambda_dependencies.is_file() and one_lambda_dependencies.stat().st_size>0:
                        command_line = [
                            sys.executable, "-m", "pip", "install",
                            "--platform", "manylinux2014_aarch64",
                            "--only-binary", ":all:",
                            "--target", str(work_folder),
                            "-r", str(one_lambda_dependencies)
                        ]
                        # *NOTE* blocking check_call is used as process is typically fast running
                        subprocess.check_call(command_line)
                    pass
                case "ts":
                    # install dependencies to build subfolder
                    zip_folder = work_folder / "zip/"
                    os.mkdir(zip_folder)
                    # *NOTE* if lambda subfolder will have package.json it'll be used instead of global one
                    # *NOTE* you can put empty package.json into function folder if it doesn't have any dependencies
                    one_lambda_dependencies = sources_folder / "package.json"
                    if not one_lambda_dependencies.is_file():
                        shutil.copy(str(ts_dependencies_list), str(work_folder))
                    curr_path = os.getcwd()
                    os.chdir(work_folder)
                    command_line = ["npm", "install"] #, "--omit", "dev"]
                    # *NOTE* blocking check_call is used as process is typically fast running
                    subprocess.check_call(command_line)
                    # compile ts to index.js (will be done by webpack)
                    # command_line = ["npx", "tsc"]
                    # subprocess.check_call(command_line)
                    command_line = ["npm", "run", "build"] #f"npm pack --pack-destination='./zip'"
                    subprocess.check_call(command_line)
                    os.chdir(curr_path)

                case "golang":
                    # *NOTE* lambda subfolder should have proper .mod file!
                    # compile go to run on ARM Lambda
                    # install dependencies to build subfolder
                    zip_folder = work_folder / "zip/"
                    os.mkdir(zip_folder)
                    curr_path = os.getcwd()
                    os.chdir(work_folder)
                    # compile ts to ARMx64 executable
                    # GOOS=linux GOARCH=arm64 go build -tags lambda.norpc -o bootstrap main.go
                    # subprocess.check_call(command_line)
                    try:
                        subprocess.check_call("GOOS=linux GOARCH=arm64 go build -tags lambda.norpc -o bootstrap main.go", shell=True)
                    except Exception as e:
                        _top_logger.warning(f"Failed to build go lambda {lambda_name} with exception {e}")
                        raise e
                    os.chdir(curr_path)
                    # now we just need to copy bootstrap to zip folder
                    shutil.copy(str(work_folder / "bootstrap"), str(zip_folder / "bootstrap"))

                case default:
                    _top_logger.warning(f"Unsupported language {language} in the {sources_folder}. IGNORED!")
                    continue
            

            try:
                shutil.copytree(work_folder / "assets", zip_folder / "assets")
            except FileExistsError:
                _top_logger.warning(f"Did not copy assets folder for {lambda_name} as assets was already there")
                pass
            except FileNotFoundError as e:
                pass
            except Exception as e:
                _top_logger.warning(f"Did not copy assets folder for {lambda_name} with exception {e}")
            # zip build to deploy folder with name according to current build (if needed)
            shutil.make_archive(
                str(deploy_folder / f"{lambda_name}_{deployment_package_name}"),
                format="zip",
                root_dir=zip_folder,
                verbose=True
            )
            # clean up build folder (just delete whole folder)
            try:
                shutil.rmtree(build_folder)
            except Exception as e:
                _top_logger.info(f"Was not able to clean up build folder with exception {e}")
                pass


