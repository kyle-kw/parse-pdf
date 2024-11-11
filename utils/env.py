
import os
from loguru import logger


def get_env(env_name, default=None, required=False, arg_formatter=None):
    rv = os.getenv(env_name)
    if required and rv is None and default is None:
        raise ValueError("'{}' environment variable is required.".format(env_name))
    elif rv is None:
        rv = default
    if arg_formatter is not None:
        rv = arg_formatter(rv)
    logger.debug(f"env_name: {env_name}, value: {rv}")
    return rv



CHUNK_SIZE_LIST = get_env("CHUNK_SIZE_LIST", "200,400,800", arg_formatter=lambda x: [int(i) for i in x.split(',')])
CHUNK_OVERLAP_LIST = get_env("CHUNK_OVERLAP_LIST", "40,80,160", arg_formatter=lambda x: [int(i) for i in x.split(',')])
TABLE_FORMAT = get_env("TABLE_FORMAT", "markdown")
DOC_SUM_NUM = get_env("DOC_SUM_NUM", 100, arg_formatter=int)


