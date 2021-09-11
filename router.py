#!/usr/bin/env python3

import time
import openstack
import logging as log
from datetime import datetime

log.basicConfig(format="%(asctime)s: %(message)s", level=log.INFO, datefmt="%Y-%m-%d %H:%M:%S")
conn = openstack.connect()


def compare_dict_change(old, new):
    return

def main(interval=3600, log_dir='./log'):

    monitoring_routers = {}
    
    while True:
        now = datetime.now()
        check_time = now.strftime("%Y-%m-%d %H:%M:%S")

        routers = conn.list_routers()
        for r in routers:
            log.debug(f'{r.created_at} {r.updated_at} {r.id} {r.name} {r.status} {r.routes} {r.project_id} {r.external_gateway_info}')
            
            routes = []
            for route in r.routes:
                destination = route['destination']
                nexthop = route['nexthop']
                routes.append(f'{destination}->{nexthop}')

            if r.external_gateway_info != None:
                external_gateway_info = {
                    'network': r.external_gateway_info['network_id'],
                    'snat': r.external_gateway_info['enable_snat'],
                    'ips': r.external_gateway_info['external_fixed_ips']
                }
            else:
                external_gateway_info = None
           
            router_interfaces = []
            r_interfaces = conn.list_router_interfaces(r)
            for ri in r_interfaces:
                router_interfaces.append(dict(ri))
                
            r_info = {
                'created_at': r.created_at,
                'updated_at': r.updated_at,
                'status': r.status,
                'project_id': r.project_id,
                'routes': routes,
                'external_gateway_info': external_gateway_info,
                'interfaces': router_interfaces
            }

            # compare diff
            diff = compare_dict_change(monitoring_routers[r.id], r_info)
            monitoring_routers[r.id] = r_info
            
            #print(f'{r_info}')
            
        time.sleep(interval)


if __name__ == '__main__':
    main()

