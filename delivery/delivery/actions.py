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
    if response.status_code != 200:
        try:
            data = response.json()
            message = json.dumps(data['message'])
        except Exception:
            response.raise_for_status()
        raise Exception(message)


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
    data = response.json()
    created = data.get('tasks')
    if tasks is None or not len(created):
        raise Exception('No tasks created.')
    num_created = len(created)
    if num_created == len(tasks):
        return
    orders = [t.get('metadata') for t in created]
    orders = [item for sublist in orders for item in sublist]
    orders = [o['value'] for o in orders if o['name'] == 'order_number']
    raise Exception('{nc} of {ns} orders created. Missing: {missing}'.format(
        nc=num_created,
        ns=len(tasks),
        missing=[t.order_number for t in tasks if t.order_number not in orders]
    ))


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
