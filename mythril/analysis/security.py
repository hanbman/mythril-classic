"""This module contains functionality for hooking in detection modules and
executing them."""
from collections import defaultdict
from ethereum.opcodes import opcodes
from mythril.analysis import modules
import pkgutil
import importlib.util
import logging

log = logging.getLogger(__name__)

OPCODE_LIST = [c[0] for _, c in opcodes.items()]


def reset_callback_modules():
    """Clean the issue records of every callback-based module."""
    modules = get_detection_modules("callback")
    for module in modules:
        module.detector.reset_module()


def get_detection_module_hooks(modules, hook_type="pre"):
    hook_dict = defaultdict(list)
    _modules = get_detection_modules(entrypoint="callback", include_modules=modules)
    for module in _modules:
        hooks = (
            module.detector.pre_hooks
            if hook_type == "pre"
            else module.detector.post_hooks
        )
        for op_code in map(lambda x: x.upper(), hooks):
            if op_code in OPCODE_LIST:
                hook_dict[op_code].append(module.detector.execute)
            elif op_code.endswith("*"):
                to_register = filter(lambda x: x.startswith(op_code[:-1]), OPCODE_LIST)
                for actual_hook in to_register:
                    hook_dict[actual_hook].append(module.detector.execute)
            else:
                log.error(
                    "Encountered invalid hook opcode %s in module %s",
                    op_code,
                    module.detector.name,
                )
    return dict(hook_dict)


def get_detection_modules(entrypoint, include_modules=()):
    """

    :param entrypoint:
    :param include_modules:
    :return:
    """
    include_modules = list(include_modules)

    _modules = []

    if not include_modules:
        for loader, module_name, _ in pkgutil.walk_packages(modules.__path__):
            if module_name != "base":
                module = importlib.import_module(
                    "mythril.analysis.modules." + module_name
                )
                if module.detector.entrypoint == entrypoint:
                    _modules.append(module)
    else:
        for module_name in include_modules:
            module = importlib.import_module("mythril.analysis.modules." + module_name)
            if module.__name__ != "base" and module.detector.entrypoint == entrypoint:
                _modules.append(module)

    log.info("Found %s detection modules", len(_modules))
    return _modules


def fire_lasers(statespace, module_names=()):
    """

    :param statespace:
    :param module_names:
    :return:
    """
    log.info("Starting analysis")

    issues = []
    for module in get_detection_modules(
        entrypoint="post", include_modules=module_names
    ):
        log.info("Executing " + module.detector.name)
        issues += module.detector.execute(statespace)

    issues += retrieve_callback_issues(module_names)
    return issues


def retrieve_callback_issues(module_names=()):
    issues = []
    for module in get_detection_modules(
        entrypoint="callback", include_modules=module_names
    ):
        log.debug("Retrieving results for " + module.detector.name)
        issues += module.detector.issues

    reset_callback_modules()
    return issues
