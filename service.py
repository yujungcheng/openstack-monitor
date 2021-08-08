#!/usr/bin/env python3

import time
import openstack
import pymysql
import queue
import threading
import logging as log
from pathlib import Path
from datetime import datetime


log.basicConfig(format="%(asctime)s: %(message)s", level=log.INFO, datefmt="%Y-%m-%d %H:%M:%S")
conn = openstack.connect()


def check_core_services(return_queue, retry=3):
    for i in range(retry):
        try:
            data = []
            services = conn.list_services()
            for s in services:
                log.debug(f'core_services: {s.id} {s.name} {s.type} {s.enabled}')
                data.append({'id': s.id, 'name': s.name, 'type': s.type, 'enabled': s.enabled})
            break
        except Exception as e:
            log.error(f'fail to list core_services({i}): {e}')
    return_queue.put({'core_services': data})

def check_hypervisors(return_queue, retry=3):
    for i in range(retry):
        try:
            data = []
            hypervisors = conn.list_hypervisors()
            for h in hypervisors:
                #print(type(h.cpu_info))
                #print(dir(h.cpu_info))
                log.debug((f'{h.id} {h.name} {h.status} {h.state} {h.vcpus} {h.vcpus_used} '
                           f'{h.memory_size} {h.memory_used} {h.local_disk_size} {h.local_disk_used} '
                           f'{h.running_vms}'))
                data.append({
                    'id': h.id,
                    'name': h.name,
                    'status': h.status,
                    'state': h.state,
                    'vcpus': h.vcpus,
                    'vcpus_used': h.vcpus_used,
                    'memory_size': h.memory_size,
                    'memory_used': h.memory_used,
                    'local_disk_size': h.local_disk_size,
                    'local_disk_used': h.local_disk_used,
                    'running_vms': h.running_vms
                })
            break
        except Exception as e:
            log.error(f'fail to list network hypervisors({i}): {e}')
    return_queue.put({'hypervisors': data})

def check_compute_services(return_queue, retry=3):
    for i in range(retry):
        try:
            data = []
            services = conn.compute.services()
            for s in services:
                log.debug(f'{s.id} {s.binary} {s.state} {s.host}')
                data.append({'id': s.id, 'name': s.binary, 'state': s.state, 'host': s.host})
            break
        except Exception as e:
            log.error(f'fail to list nova services({i}): {e}')
    return_queue.put({'compute_services': data})

def check_network_agents(return_queue, retry=3):
    for i in range(retry):
        try:
            data = []
            agents = conn.network.agents()
            for a in agents:
                log.debug((f'{a.id} {a.binary} {a.is_admin_state_up} {a.is_alive} '
                           f'{a.host} {a.last_heartbeat_at} {a.started_at} {a.created_at}'))
                data.append({
                    'id': a.id,
                    'name': a.binary,
                    'state': a.is_admin_state_up,
                    'alive': a.is_alive,
                    'host': a.host,
                    'last_heartbeat_at': a.last_heartbeat_at,
                    'started_at': a.started_at,
                    'created_at': a.created_at
                })
            break
        except Exception as e:
            log.error(f'fail to list network agents({i}): {e}')
    return_queue.put({'network_agents': data})


def main(interval=3600, log_dir='./log'):
    region = conn._compute_region
    log.info(f'Start monitoring services, region={region}, interval={interval}')

    core_services_log_file = "services.core-services.log"
    compute_services_log_file = "services.compute-services.log"
    hypervisors_log_file = "services.hypervisors.log"
    network_agents_log_file = "services.network-agents.log"

    return_queue = queue.Queue()
    while True:
        #ts = datetime.now().timestamp()
        now = datetime.now()
        check_time = now.strftime("%Y-%m-%d %H:%M:%S")

        core_services_t = threading.Thread(target=check_core_services, args=(return_queue,))
        hypervisors_t = threading.Thread(target=check_hypervisors, args=(return_queue,))
        nova_services_t = threading.Thread(target=check_compute_services, args=(return_queue,))
        network_agents_t = threading.Thread(target=check_network_agents, args=(return_queue,))

        core_services_t.start()
        hypervisors_t.start()
        nova_services_t.start()
        network_agents_t.start()

        count_t = threading.active_count()
        log.debug(f'Active threads {count_t}')

        for i in range(4):  # monitoring 4 services
            data = return_queue.get()
            if 'core_services' in data:
                log.debug(f"Core Services:\n{data['core_services']}")
                target_log_file = core_services_log_file
                target_data = data['core_services']
            elif 'compute_services' in data:
                log.debug(f"Compute Services:\n{data['compute_services']}")
                target_log_file = compute_services_log_file
                target_data =  data['compute_services']
            elif 'hypervisors' in data:
                log.debug(f"Hypervisors:\n{data['hypervisors']}")
                target_log_file = hypervisors_log_file
                target_data =  data['hypervisors']
            elif 'network_agents' in data:
                log.debug(f"Network Agents:\n{data['network_agents']}")
                target_log_file = network_agents_log_file
                target_data =  data['network_agents']

            Path(log_dir).mkdir(parents=True, exist_ok=True)
            target_log_file = f'{log_dir}/{region}.{target_log_file}'
            with open(target_log_file, 'a') as f:
                for item in target_data:
                    l_data = []
                    for key, value in item.items():
                        l_data.append(f"{key}={value}")
                    s_data = f','.join(l_data)
                    f.write(f'{check_time} {s_data}\n')

        if threading.active_count() == 1:
            log.debug(f'Checking threads finished')

        time.sleep(interval)


if __name__ == '__main__':
    main()

