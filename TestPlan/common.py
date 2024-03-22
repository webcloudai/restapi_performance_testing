'''
© 2024 Daniil Sokolov <{$contact}>
MIT License
'''
import re
import logging
_top_logger = logging.getLogger(__name__)


def clean_name(source:str)->str:
    ''' some of names has <number>_ prefix '''
    if not isinstance(source, str):
        raise ValueError(f"clean_name: Incorrect incoming value {source} for incoming string")
    # we need to check if source fit into RegEx with <number>_ prefix pattern
    prefix_lookup = re.match(r"^\d+_", source)
    if prefix_lookup is None:
        return source
    return source[prefix_lookup.span()[1]:]
