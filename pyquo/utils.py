#!/usr/bin/python3

import os
import re
import json
import unicodedata
from pyquo import defaults

DEFAULT_PROPERTIES_FILE = os.path.join(os.environ['HOME'], defaults.PROPERTIES)


def get_properties(properties_file=DEFAULT_PROPERTIES_FILE):
    if os.path.exists(properties_file):
        with open(properties_file) as f:
            return json.loads(f.read())
    return {}


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
    """
    normalized_value = unicodedata.normalize(
        'NFKD', value).encode('ascii', 'ignore').decode('ascii')
    stripped_value = re.sub('[^\w\s-]', '', normalized_value).strip().lower()
    return re.sub('[-\s]+', '-', stripped_value)


def mkdir(directory):
    """ Make a directory, check and throw an error if failed. """
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError:
            if not os.path.isdir(directory):
                raise

def parse_args(parser):
    args = vars(parser.parse_args())
    try:
        command = args.pop('command')
    except KeyError:
        parser.print_help()
        parser.exit()
    return command, args
