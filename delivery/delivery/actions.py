import datetime
import json
from os import path
from typing import Set, Union, Sequence, Optional, List, Dict
import requests
from django.conf import settings
from django.db.models.functions import Upper

from delivery.utils.typing import none_throws

from .models import Delivery
from .clover import (
    search_clover_by_dates,
    get_delivery_type,
    request_clover_customer_list,
    parse_shopify_order_number,
)
from .shopify import (
    ShopifyOrderInfo,
    get_data_from_shopify_by_name,
    get_data_by_time_range as get_shopify_data_by_time_range,
)


def create_onfleet_task_from_order(obj):
    if obj.address_line_1 is None:
        raise ValueError("No address associated with order")
    response = requests.post(
        path.join(settings.ONFLEET_INTEGRATION_API, "tasks"),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
        data=json.dumps(obj.serialize_for_onfleet()),
    )
    if response.status_code != 200:
        try:
            data = response.json()
            message = json.dumps(data["message"])
        except Exception:
            response.raise_for_status()
        raise Exception(message)


def create_onfleet_tasks_from_shift(obj):
    tasks = obj.delivery_set.exclude(address_line_1=None)
    if tasks.count() < 1:
        raise ValueError("No valid orders in this shift")
    response = requests.post(
        path.join(settings.ONFLEET_INTEGRATION_API, "tasks", "batch"),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
        data=json.dumps({"tasks": [t.serialize_for_onfleet() for t in tasks]}),
    )
    response.raise_for_status()
    data = response.json()
    created = data.get("tasks")
    if tasks is None or not created:
        raise Exception("No tasks created.")
    num_created = len(created)
    if num_created == len(tasks):
        return
    orders = [t.get("metadata") for t in created]
    orders = [item for sublist in orders for item in sublist]
    orders = [o["value"] for o in orders if o["name"] == "order_number"]
    raise Exception(
        "{nc} of {ns} orders created. Missing: {missing}".format(
            nc=num_created,
            ns=len(tasks),
            missing=[t.order_number for t in tasks if t.order_number not in orders],
        )
    )


def get_onfleet_trucks():
    response = requests.get(
        path.join(settings.ONFLEET_INTEGRATION_API, "workers"),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
    )
    content = response.json()
    if 'message' in content and 'error' in content['message']:
        raise Exception(content['message']['message'])

    workers = {x["id"]: x for x in content if len(x["tasks"])}
    response = requests.get(
        path.join(settings.ONFLEET_INTEGRATION_API, "teams"),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
    )
    teams = {
        x["id"]: x for x in response.json() if any((w in workers) for w in x["workers"])
    }
    response = requests.get(
        path.join(settings.ONFLEET_INTEGRATION_API, "tasks"),
        auth=requests.auth.HTTPBasicAuth(settings.ONFLEET_API_KEY, None),
        params={"from": "1514793600000", "state": "1"},
    )
    tasks = {}
    for task in response.json():
        tasks[task["id"]] = task
        order_metadata = next(
            (m for m in task["metadata"] if m["name"] == "order_number"), None
        )
        if order_metadata is None:
            continue
        order_number = order_metadata["value"]
        try:
            order = Delivery.objects.get(order_number=order_number)
        except Delivery.DoesNotExist:
            continue
        task["order"] = order
    return (teams, workers, tasks)


def search_clover_orders(
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
    include_processed: bool = False,
) -> Sequence[Delivery]:
    # get data
    clover_orders = search_clover_by_dates(start_date, end_date)
    shopify_delivery_orders: List[ShopifyOrderInfo] = list(
        get_shopify_data_by_time_range(
            start_date, end_date=end_date, delivery_only=True
        )
    )
    shopify_names = [o.name for o in shopify_delivery_orders]

    # sort orders by clover or shopify
    clover_delivery_orders: List[Dict] = []
    clover_from_shopify: Dict[str, Dict] = {}
    missing_shopify_names: List[str] = []
    for o in clover_orders:
        shopify_name = parse_shopify_order_number(o)
        if shopify_name:
            clover_from_shopify[shopify_name] = o
            # get anything that might be delayed out of the time range
            if shopify_name not in shopify_names and get_delivery_type(o):
                missing_shopify_names.append(shopify_name)
            continue
        if get_delivery_type(o):
            clover_delivery_orders.append(o)
    if missing_shopify_names:
        for name, v in get_data_from_shopify_by_name(
            missing_shopify_names, delivery_only=True
        ).items():
            if v is None:
                raise ValueError(f"Unable to find Shopify order {name}")
            shopify_delivery_orders.append(v)

    # if we're empty, return
    if not clover_delivery_orders and not shopify_delivery_orders:
        return []

    scheduled_clover_orders = Delivery.objects.annotate(
        clover_id=Upper("order_number")
    ).filter(clover_id__in=[o["id"] for o in clover_delivery_orders])
    scheduled_clover_orders_dict: Dict[str, Delivery] = {
        o.clover_id: o for o in scheduled_clover_orders
    }

    scheduled_shopify_orders = Delivery.objects.filter(
        online_id__in=[o.online_id for o in shopify_delivery_orders]
    )
    scheduled_shopify_orders_dict: Dict[str, Delivery] = {
        none_throws(o.online_id): o for o in scheduled_shopify_orders
    }

    # TEMP: prepopulate the customer cache because the clover orders call doesn't return details
    incomplete_customers: Set[str] = set()
    for o in clover_delivery_orders:
        if "customers" not in o:
            continue
        customers = o["customers"]["elements"]
        if len(customers) != 1:
            continue
        customer = customers[0]
        # treat as proxy for complete
        if "addresses" in customer:
            continue
        incomplete_customers.add(customer["id"])

    _ = request_clover_customer_list(list(incomplete_customers))
    # END TEMP

    orders: List[Delivery] = []
    for co in clover_delivery_orders:
        if co["id"] in scheduled_clover_orders_dict:
            if include_processed:
                orders.append(scheduled_clover_orders_dict[o["id"]])
        else:
            delivery = Delivery.create_from_clover(co, skip_items=True)
            delivery.delivery_type = none_throws(get_delivery_type(co))
            orders.append(delivery)

    for so in shopify_delivery_orders:
        if so.online_id in scheduled_shopify_orders_dict:
            if include_processed:
                orders.append(scheduled_shopify_orders_dict[so.online_id])
        else:
            clover_order = clover_from_shopify.get(so.name)
            if clover_order:
                order_number = clover_order["id"]
            else:
                order_number = f"Shopify-{so.name}"
            delivery = Delivery(order_number=order_number, online_id=so.online_id)
            delivery.load_from_shopify_info(so)
            orders.append(delivery)

    orders.sort(key=lambda o: o.created_at, reverse=True)
    return orders
