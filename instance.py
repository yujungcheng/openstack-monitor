#!/usr/bin/env python3

import sys
import time
import queue
import threading
import argparse
import openstack
import logging as log
from datetime import datetime
from pathlib import Path


conn = openstack.connect()
log.basicConfig(format="%(asctime)s: %(message)s", level=log.INFO, datefmt="%Y-%m-%d %H:%M:%S")
monitor_interval = 600

class Monitor(threading.Thread):
    ''' Worker thread with return value '''
    def __init__(self, func, result_queue, *args, wait=monitor_interval, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = result_queue
        self._stop = threading.Event()
        self._wait = wait
        self.running = False

    def run(self):
        self.running = True
        while not self._stop.is_set():
            try:
                result = self.func(*self.args, **self.kwargs)
                self.result.put(result)
            except Exception as e:
                log.error(f'Worker run failed: {e}')
            self._stop.wait(self._wait)

    def stop(self):
        self.running = False
        self._stop.set()
        super().join(0)


def servers(filters={}):
    conn = openstack.connect()
    if 'host' in filters:
        return conn.compute.servers(details=True, all_projects=True, host=filters['host'])
    elif 'project' in filters:
        return conn.compute.servers(details=True, all_projects=True, project_id=filters['project'])        
    elif 'uuid' in filters:
        instances = []
        for uuid in filters['uuid']:
            i = conn.compute.servers(details=True, all_projects=True, uuid=uuid)
            for s in i:
                instances.append(s)
        return instances

def list_instances_by_filters(filters={}):
    data = []
    for i in range(3):
        try:
            instances = servers(filters=filters)
            if instances == None:
                raise Exception("Unable to fetch instances")
            for s in instances:
                network = {}
                if s.addresses == None:
                    addresses = []
                else:
                    addresses = s.addresses
                for net_name, net_ips in addresses.items():
                    ips = {}
                    for ip in net_ips:
                        ips[ip['OS-EXT-IPS-MAC:mac_addr']] = ip['addr']
                    network[net_name] = ips
                if s.security_groups == None:
                    security_groups = []
                else:
                    security_groups = [s['name'] for s in s.security_groups]
                log.debug(f'{s.id} {s.name} {s.vm_state} {s.task_state} {network} {security_groups}')
                data.append({'id': s.id, 
                             'name': s.name, 
                             'vm_state': s.vm_state, 
                             'task_state': s.task_state,
                             'network': network,
                             'security_groups': security_groups})
            break
        except Exception as e:
            log.error(f'list_instances_by_filters failed{i}, {filters}: {e}')
            time.sleep(1)
    return data

def list_instances_by_compute_node(host):
    result = {'host': host}
    result['data'] = list_instances_by_filters(filters={'host': host})
    now = datetime.now()
    result['checked_at'] = now.strftime("%Y-%m-%d %H:%M:%S")
    return result

def list_instances_by_project(project_id):    
    result = {'project': project_id}
    result['data'] = list_instances_by_filters(filters={'project': project_id})
    now = datetime.now()
    result['checked_at'] = now.strftime("%Y-%m-%d %H:%M:%S")
    return result

def list_instances_by_uuid(uuid=[]):
    result = {'uuid': uuid}
    result['data'] = list_instances_by_filters(filters={'uuid': uuid})
    now = datetime.now()
    result['checked_at'] = now.strftime("%Y-%m-%d %H:%M:%S")
    return result

def process_result(result_queue, log_dir='./log'):
    region = conn._compute_region
    while True:
        result = result_queue.get()
        if result == None:
            break
        checked_at = result['checked_at']
        data_count = len(result['data'])
        if 'host' in result:
            log.info(f"Host={result['host']} Count={data_count}")
            logfile = 'instances.by-host.log'
            head_line = f"{checked_at} {result['host']}"
        if 'project' in result:
            log.info(f"Project={result['project']} Count={data_count}")
            logfile = 'instances.by-project.log'
            head_line = f"{checked_at} {result['project']}"
        if 'uuid' in result:
            log.info(f"UUID={result['uuid']} Count={data_count}")
            logfile = 'instances.by-uuid.log'
            head_line = f"{checked_at} {result['uuid']}"
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        target_logfile = f'{log_dir}/{region}.{logfile}'
        with open(target_logfile, 'a') as f:
            f.write(f"{head_line}\n")
            for instance in result['data']:
                line_items = []
                for key, value in instance.items():
                    line_items.append(f"{key}={value}")
                line_string = f','.join(line_items)
                f.write(f"{line_string}\n")
            

def main(args):
    result_queue = queue.Queue()
    monitors = {}
    try:
        # start result processing thread
        process_result_t = threading.Thread(target=process_result, args=(result_queue,))
        process_result_t.start()
        
        # start monitoring threads
        while True:
            if args['host']:  # by compute node
                hosts = []
                services = conn.compute.services()
                for s in services:
                    if s.binary == "nova-compute":
                        if s.host not in hosts:
                            hosts.append(s.host)      
                        if s.host not in monitors:
                            log.info(f'start compute node {s.host} monitoring')
                            m = Monitor(list_instances_by_compute_node, result_queue, s.host)
                            monitors[s.host] = m
                            m.start()
                            time.sleep(1)
                monitoring_hosts = list(monitors.keys())
                for h in monitoring_hosts:
                    if h not in hosts:
                        log.info(f'compute node {h} not exist, remove {h} monitoring.')
                        monitors[h].stop()
                        del(monitors[h])

            elif args['project']:  # by project
                project_ids = []
                projects = conn.identity.projects()
                for p in projects:
                    if p.name == 'service':  # skip service project
                        continue
                    if p.id not in project_ids:
                        project_ids.append(p.id)
                    if p.id not in monitors:
                        log.info(f'start project {p.name} ({p.id}) monitoring')
                        m = Monitor(list_instances_by_project, result_queue, p.id)
                        monitors[p.id] = m
                        m.start()
                        time.sleep(1)
                monitoring_projects = list(monitors.keys())
                for p in monitoring_projects:
                    if p not in project_ids:
                        log.info(f'project {p.name} not exist, remove {p.name} monitoring')
                        monitors[p].stop()
                        del(monitors[p])

            else:  # by uuid, give a list of instance uuid
                uuid = args['uuid']
                if len(uuid) != 0: 
                    print(f'{uuid}')
                    log.info(f'start instance {uuid} monitoring')
                    if 'uuid' not in monitors:
                        m = Monitor(list_instances_by_uuid, result_queue, uuid)
                        monitors['uuid'] = m
                        m.start()
                else:
                    log.info(f'No monitoring filters supplied')
                    break
                
            time.sleep(monitor_interval)
    except Exception as e:
        log.error(f'Error: {e}')
    finally:
        for host, monitor in monitors.items():
            monitor.stop()
        result_queue.put(None)


if __name__ == '__main__':
    parser =  argparse.ArgumentParser(description='openstack instance monitor')
    parser.add_argument('--host', action='store_true')
    parser.add_argument('--project', action='store_true')
    parser.add_argument('uuid', nargs='*')
    args = vars(parser.parse_args(sys.argv[1:]))
    main(args)
