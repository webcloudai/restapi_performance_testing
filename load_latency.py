'''
© 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
MIT License
'''
from typing import Union, Dict, List
import sys
import argparse
from pathlib import Path
import json
import re
from jinja2 import Environment, PackageLoader, select_autoescape, Undefined
from jinja2.nativetypes import NativeEnvironment
from TestPlan import TestPlan
from TestPlan.reporter import ReporterJsonRecords, ReportAggregatorCsv, LogRecordType, ReportAggregatorXlsx
import logging
# NOTE that we're logging into stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger(__name__)

DEFAULT_TEST_TEMPLATE = "load_test.json.jinja"
loaded_file_variables:Dict[str, dict] = {}
FILE_VAR_RE = re.compile(r"^\{file\}:\/\/(.+)->(.+)\/\{file_end\}(.*)$")

class PreserveUndefined(Undefined):
    ''' Custom Undefined handler preserving undefined jinja variables '''
    # inspired by jinja2.DebugUndefined implementation
    def __str__(self) -> str:
        if self._undefined_name:
            message = f"{self._undefined_name}"
        else:
            message = f"jinja error"
        return f"{{{{ {message} }}}}"

def recursive_jinja(source:Union[Dict,List], variables:dict={})->Union[Dict, List]:
    ''' '''
    jjenv = NativeEnvironment(undefined=PreserveUndefined) #undefined=DebugUndefined)
    vars:dict = {
        **variables,
        **(source.get("VARIABLES",{}) if isinstance(source, dict) else {})
    }

    if isinstance(source, dict):
        result = {}
        for k,v in source.items():
            if isinstance(k,str):
                if k.startswith("_"):
                    # IGNORE ALL KEYS STARTING FROM underscore ('_')
                    continue
                key = jjenv.from_string(k).render(**vars)
            else:
                key = k
            if isinstance(v, str):
                if v.startswith("{file}://"):
                    # we've got a file variable
                    matching_groups = FILE_VAR_RE.search(v)
                    if not matching_groups:
                        raise ValueError(f"Incorrect file variable format - {v}")
                    if matching_groups.group(1) not in loaded_file_variables:
                        with open(matching_groups.group(1)) as f:
                            loaded_file_variables[matching_groups.group(1)] = json.load(f)
                    val = loaded_file_variables[matching_groups.group(1)].get(matching_groups.group(2), None)
                    val += matching_groups.group(3) if matching_groups.group(3) else ""
                    if val is None:
                        raise ValueError(f"File variable {matching_groups.group(2)} not found in {matching_groups.group(1)}")
                    val = jjenv.from_string(val).render(**vars)
                else:
                    val = jjenv.from_string(v).render(**vars)
            elif isinstance(v, (dict, list)):
                val = recursive_jinja(v, vars)
            else:
                val = v
            result[key] = val
    elif isinstance(source, list):
        result = [
            jjenv.from_string(v).render(**vars) if isinstance(v, str)
            else recursive_jinja(v, vars) if isinstance(v, (dict, list))
            else v
            for v in source]
    else:
        raise ValueError(f"Incorrect source for recursive_jinja - {source}")

    return result

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='''Run set of http requests using Template as a definition and store the results in the output file''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''

        
examples:

python load_latency.py
    This will start from default template {DEFAULT_TEST_TEMPLATE} and proceed with test execution

python load_latency.py --dry
    This will start from default template {DEFAULT_TEST_TEMPLATE} but will not execute the test

python load_latency.py --final load_test.FINAL.json
    This will skip all template handling and use mentioned file to proceed with test execution


'''
    )

    parser.add_argument("--template", "-t", dest="template_file", required=False, default=DEFAULT_TEST_TEMPLATE, help=f"load test template. Must be located in the 'templates' folder! Default is '{DEFAULT_TEST_TEMPLATE}'")
    parser.add_argument("--input", "-i", dest="input_file", required=False, default=None, help="load test definition. None by default as will be generated from template. Intermediate option convenient for template debugging.")
    parser.add_argument("--final", "-f", dest="final_input_file", required=False, default=None, help="final definition of load test. None by default as will be generated from template. Best option if you don't want ti spent time on template handling.")
    parser.add_argument("--report", "-o", dest="report_file", required=False, default="load_test_report.xlsx", help="location of generated report file. Default is 'load_test_report.xlsx'")
    parser.add_argument("--dry", "-d", dest="dry", required=False, action="store_true", help="will just generate test plan but do not run it. Best option to validate your template.")
    parser.add_argument("--dry_run", "-dr", dest="dry_run", required=False, action="store_true", help="will run the test but without real requests to the API. Best debugging option.")
    parser.add_argument("--aggregate_only", "-a", dest="aggregate_only", required=False, action="store_true", help="will run only the aggregation of already collected data. Best option when test was stopped but some data collected.")

    args = parser.parse_args()
    return args

if __name__=="__main__":
    my_args = parse_arguments()
    template_file = my_args.template_file or (DEFAULT_TEST_TEMPLATE if my_args.input_file is None else None)
    report_file = Path(my_args.report_file)
    dry_run = my_args.dry_run or False
    dry = my_args.dry or False
    final_input_file = my_args.final_input_file
    aggregate_only = my_args.aggregate_only or False

    # Create JSON Reporter (will store every record as a separate file)
    myReporter = ReporterJsonRecords(
        reporter_options={
            "name":final_input_file,
            "logs_folder": str(Path("temp_logs") / "log_records"),
            "errs_folder": str(Path("temp_logs") / "log_errors")
        }
    )

    if not aggregate_only:
        if not isinstance(final_input_file, str) or len(final_input_file)==0:
            # we don't have final input file so will create from template or from input_file
            if isinstance(template_file, str):
                input_file = template_file.replace(".jinja", "")
                if isinstance(my_args.input_file, str):
                    _top_logger.warning(f"You have provided both template and input file. Input file will be ignored! Generated {input_file} will be used instead")
                env = Environment(
                    loader=PackageLoader("load_latency"),
                    autoescape=select_autoescape(),
                    undefined=PreserveUndefined
                )
                try:
                    template = env.get_template(template_file)
                except Exception as e:
                    _top_logger.error(f"Fail to read {template_file} with exception {e}")
                    exit(-1)
                try:
                    rendered_template = template.render()
                except Exception as e:
                    _top_logger.error(f"Fail to render {template_file} with exception {e}")
                    exit(-1)
                try:
                    rendered_template_obj = json.loads(rendered_template)
                except Exception as e:
                    _top_logger.error(f"Template {template_file} rendered but resulting file is not correct! Exception {e}")
                    err_file = template_file.replace(".jinja", ".wrong.json")
                    with open(err_file, "w") as f:
                        f.write(template.render())
                    _top_logger.error(f"For your convenience incorrect file is available at {err_file}")
                    exit(-1)
                with open(input_file, "w") as f:
                    json.dump(rendered_template_obj, f, indent=3)
                _top_logger.info(f"Input file {input_file} generated and stored for use")
            elif isinstance(my_args.input_file, str):
                input_file = my_args.input_file
                _top_logger.info(f"No template file provided! {input_file} will be used as a source")
            else:
                _top_logger.error("No template file or input file were provided. Exiting")
                exit(-1)
            
            # we have an input file which can have multiple 'VARIABLES' in the nested structures
            # to have a final version we need to perform recursive parsing
            with open(input_file, "r") as f:
                input_object = json.load(f)

            final_input = recursive_jinja(input_object)
            final_input = recursive_jinja(final_input)
            final_input = recursive_jinja(final_input)

            final_input_file = input_file.replace(".json", ".FINAL.json")
        
            with open(final_input_file, "w") as f:
                json.dump(final_input, f, indent=3)

        else:
            with open(final_input_file, "r") as f:
                final_input = json.load(f)

        # At this moment we have cleaned and parsed final_input
        # So we have Test Plan definition ready
        if dry:
            _top_logger.info(f"Dry run. Test plan has been generated but not run. See {input_file} and {final_input_file}")
            exit(0)
        
        # run the Test Plan
        myTestPlan = TestPlan(Path(final_input_file).stem, final_input if isinstance(final_input,dict) else {}, myReporter)
        myTestPlan.execute(dry_run=dry_run)

    # run report aggregation
    match report_file.suffix:
        case ".csv":
            myReportAggregator = ReportAggregatorCsv()
        case ".xlsx":
            myReportAggregator = ReportAggregatorXlsx()
        case _:
            raise ValueError(f"Reporter aggregator for {report_file.suffix} is not available")

    myReportAggregator.aggregate(
        source=myReporter,
        record_type=LogRecordType.LATENCY,
        destination=report_file,
    )

    print("+++COMPLETED+++")