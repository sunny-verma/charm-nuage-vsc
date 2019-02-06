#!/usr/bin/python
from charmhelpers.core import (
    unitdata,
)
from charmhelpers.core.hookenv import (
    config,
    log,

)


def config_value_changed(option):
    """
    Determine if config value changed since last call to this function.
    """
    hook_data = unitdata.HookData()
    with hook_data():
        db = unitdata.kv()
        current = config(option)
        saved = db.get(option)
        db.set(option, current)
        if saved is None:
            return True
        log("config_value_changed {}:{}".format(option, (current != saved)))
        return current != saved


def get_db_value(option):
    """
    Determine if config value changed since last call to this function.
    """
    hook_data = unitdata.HookData()
    with hook_data():
        db = unitdata.kv()
        return db.get(option)


def has_db_value(option):
    """
    Determine if config value changed since last call to this function.
    """
    hook_data = unitdata.HookData()
    with hook_data():
        db = unitdata.kv()
        saved = db.get(option)
        if saved is not None:
            return True
        return False


def set_db_value(option, value):
    """
    Determine if config value changed since last call to this function.
    """
    hook_data = unitdata.HookData()
    with hook_data():
        db = unitdata.kv()
        db.set(option, value)
