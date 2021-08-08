#!/usr/bin/env python3

import os
import logging 

from datetime import datetime

from keystoneauth1 import session
from keystoneauth1.identity import v3
from keystoneauth1.identity import v2


def get_session():
    auth_url = os.environ['OS_AUTH_URL']
    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    if "OS_PROJECT_NAME" in os.environ:
        project_name = os.environ['OS_PROJECT_NAME']
    elif "OS_TENANT_NAME" in os.environ:
        project_name = os.environ['OS_TENANT_NAME']
    if "OS_PROJECT_ID" in os.environ:
        project_id = os.environ['OS_PROJECT_ID']
    elif "OS_TENANT_ID" in os.environ:
        project_id = os.environ['OS_TENANT_ID']

    if auth_url.endswith('/v2.0') or auth_url.endswith('/v2.0/'):
        auth = v2.Password(auth_url=auth_url,
                           username=username,
                           password=password,
                           tenant_name=project_name)
        print("  * use v2 auth password")
    else:
        if not (auth_url.endswith('/v3') or auth_url.endswith('/v3/')):
            if auth_url[-1] == '/':
                auth_url += 'v3'
            else:
                auth_url += '/v3'
        auth = v3.Password(auth_url=auth_url,
                           username=username,
                           password=password,
                           project_name=project_name,
                           user_domain_id="default",
                           project_domain_id="default")
        print("  * use v3 auth password")
    return session.Session(auth=auth)


def get_log(level=None):
    if level == None:
        log_level = logging.INFO
    elif level == "debug":
        log_level = logging.DEBUG
    elif level == "warning":
        log_level = logging.WARNING
    elif level == "error":
        log_level = logging.ERROR
    elif level == "critical":
        log_level = logging.CRITICAL
    return logging.basicConfig(format="%(asctime)s: %(message)s", level=log_level, datefmt="%Y-%m-%d %H:%M:%S")

def get_datetime_now():
    now = datetime.now()
    return now.strftime("%Y-%m-%d, %H:%M:%S")

