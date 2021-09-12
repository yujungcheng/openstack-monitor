#!/usr/bin/env python3

import sys
import time
import signal
import queue
import threading
import logging as log
import openstack
from pathlib import Path
from datetime import datetime


log.basicConfig(format="%(asctime)s: %(message)s", level=log.INFO, datefmt="%Y-%m-%d %H:%M:%S")
conn = openstack.connect()


class Worker(threading.Thread):
    def __init__(self, func, queue=None, interval=3600, retry=3, args=(), kwargs={}):
        super().__init__()
        self.func = func
        self.interval = interval
        self.queue = queue
        self.retry = retry
        self.args = args
        self.kwargs = kwargs
        self._stop_event = threading.Event()

    def run(self):
        log.info(f'worker start.')
        while not self._stop_event.is_set():
            for i in range(3):
                try:
                    now = datetime.now()
                    data = self.func(*self.args, **self.kwargs)
                    data['check_time'] = now.strftime("%Y-%m-%d %H:%M:%S")
                    self.queue.put(data)
                    break
                except Exception as e:
                    log.error(f'{self.func.__name__} failed({i}): {e}')
            self._stop_event.wait(self.interval)

    def stop(self):
        log.info(f'stop run.')
        self._stop_event.set()
        super().join(0)


def check_projects():
    data = []
    projects = conn.identity.projects()
    for p in projects:
        log.debug(f'{p.id} {p.name} {p.is_enabled}')
        data.append({'id': p.id, 'name': p.name, 'enabled': p.is_enabled})
    return {'projects': data}

def check_users():
    data = []
    for u in conn.list_users():
        log.debug(f'{u.id} {u.name}')
        data.append({'id': u.id, 'name': u.name})
    return {'users': data}

def check_roles():
    data = []
    roles = conn.list_roles()
    for r in roles:
        log.debug(f'{r.id} {r.name}')
        data.append({'id': r.id, 'name': r.name})
    return {'roles': data}

def check_role_assignments():
    data = []
    role_assignments = conn.list_role_assignments()
    for r in role_assignments:
        log.debug(f'{r.id} {r.project} {r.user}')
        data.append({'user_id': r.user, 'role_id': r.id, 'project_id': r.project})
    return {'role_assignments': data}


def main(interval=3600, log_dir='./log'):
    region = conn._compute_region
    log.info(f'Start monitoring project users, region={region}, interval={interval}')

    projects_log_file = 'projects.log'
    users_log_file = 'projects.users.log'
    roles_log_file = 'projects.roles.log'
    role_assignments_log_file = 'projects.role-assignments.log'

    data_queue = queue.Queue()
    projects_t = Worker(check_projects, queue=data_queue, interval=interval)
    users_t = Worker(check_users, queue=data_queue, interval=interval)
    roles_t = Worker(check_roles, queue=data_queue, interval=interval)
    role_assignments_t = Worker(check_role_assignments, queue=data_queue, interval=interval)

    projects_t.start()
    users_t.start()
    roles_t.start()
    role_assignments_t.start()

    while True:
        try:
            data = data_queue.get()
        except KeyboardInterrupt:
            log.warning(f'keyboard interrupt detected. stopping.')
            break
        check_time = data['check_time']
        if 'projects' in data:
            target_data = data['projects']
            log.debug(f'Projects count: {len(target_data)}\n')
            target_log_file = projects_log_file
        elif 'users' in data:
            target_data = data['users']
            log.debug(f'Users count: {len(target_data)}\n')
            target_log_file = users_log_file
        elif 'roles' in data:
            target_data = data['roles']
            log.debug(f'Roles count: {len(target_data)}\n')
            target_log_file = roles_log_file
        elif 'role_assignments' in data:
            target_data = data['role_assignments']
            log.debug(f'Role Assignments count: {len(target_data)}')
            target_log_file = role_assignments_log_file
        else:
            log.error(f'undefined target data key. {data.keys()}')
            continue

        Path(log_dir).mkdir(parents=True, exist_ok=True)
        target_log_file = f'{log_dir}/{region}.{target_log_file}'
        with open(target_log_file, 'a') as f:
            for item in target_data:
                l_data = []
                for key, value in item.items():
                    l_data.append(f"{key}={value}")
                s_data = f','.join(l_data)
                f.write(f'{check_time} {s_data}\n')

    projects_t.stop()
    users_t.stop()
    roles_t.stop()
    role_assignments_t.stop()


if __name__ == '__main__':
    main()

