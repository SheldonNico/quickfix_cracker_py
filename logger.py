from __future__ import annotations
import typing as t
import logging, sys

_logger = logging.getLogger("tdworkflow")

def info(msg: str, *args: t.Any, **kwargs: t.Any) -> None:
    if _logger.isEnabledFor(logging.INFO): _logger._log(logging.INFO, msg, args, **kwargs)

def debug(msg: str, *args: t.Any, **kwargs: t.Any) -> None:
    if _logger.isEnabledFor(logging.DEBUG): _logger._log(logging.DEBUG, msg, args, **kwargs)

def error(msg: str, *args: t.Any, **kwargs: t.Any) -> None:
    if _logger.isEnabledFor(logging.ERROR): _logger._log(logging.ERROR, msg, args, **kwargs)

def setup(level: int = logging.DEBUG) -> None:
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format='[%(asctime)s %(levelname)-7s %(module)s::%(funcName)s] %(message)s',
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

