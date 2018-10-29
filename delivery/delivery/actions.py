import json
from os import path
import requests
from django.conf import settings

from .models import Delivery

def create_onfleet_task_from_order(obj):
    if obj.address_line_1 is None:
        raise ValueError('No address associated with order')
    response = requests.post(
        path.join(settings.ONFLEET_INTEGRATION_API, 'tasks'),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
        data=json.dumps(obj.serialize_for_onfleet())
    )
    response.raise_for_status()
    # task_data = response.json()


def create_onfleet_tasks_from_shift(obj):
    tasks = obj.delivery_set.exclude(address_line_1=None)
    if tasks.count() < 1:
        raise ValueError('No valid orders in this shift')
    response = requests.post(
        path.join(settings.ONFLEET_INTEGRATION_API, 'tasks', 'batch'),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
        data=json.dumps({
            'tasks': [t.serialize_for_onfleet() for t in tasks]
            })
    )
    response.raise_for_status()

def get_onfleet_trucks():
    response = requests.get(
        path.join(settings.ONFLEET_INTEGRATION_API, 'workers'),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
    )
    workers = {x['id']: x for x in response.json() if len(x['tasks'])}
    response = requests.get(
        path.join(settings.ONFLEET_INTEGRATION_API, 'teams'),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
    )
    teams = {x['id']: x for x in response.json() if any((w in workers) for w in x['workers'])}
    response = requests.get(
        path.join(settings.ONFLEET_INTEGRATION_API, 'tasks'),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
        params={
            'from': '1514793600000',
            'state': 1,
        }
    )
    tasks = {}
    for task in response.json():
        tasks[task['id']] = task
        order_metadata = next((m for m in task['metadata'] if m['name'] == 'order_number'), None)
        if order_metadata is None:
            continue
        order_number = order_metadata['value']
        try:
            order = Delivery.objects.get(order_number=order_number)
        except Delivery.DoesNotExist:
            continue
        task['order'] = order
    return (teams, workers, tasks)
