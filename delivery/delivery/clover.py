from os import path
from typing import Sequence
import requests
from django.conf import settings
from django.core.cache import cache


def request_clover(url, params):
    if not settings.CLOVER_API_KEY:
        raise ValueError("Environment CLOVER_API_KEY not set.")
    headers = {
        "Content-Type": "Application/JSON",
        "Authorization": "Bearer " + settings.CLOVER_API_KEY,
    }
    return requests.get(
        url,
        params=params,
        headers=headers,
    )


def request_clover_orders(order_number=None, filters=None, offset=None, limit=None):
    if not settings.CLOVER_MERCHANT_ID:
        raise ValueError("Environment CLOVER_MERCHANT_ID not set.")
    if not settings.CLOVER_INTEGRATION_API:
        raise ValueError("Environment CLOVER_INTEGRATION_API not set.")
    orders_url = path.join(
        settings.CLOVER_INTEGRATION_API,
        "merchants",
        settings.CLOVER_MERCHANT_ID,
        "orders",
    )
    if order_number:
        orders_url = path.join(orders_url, order_number.upper())

    order_params = {"expand": "lineItems,customers"}
    if filters:
        order_params["filter"] = filters
    if limit:
        order_params["limit"] = limit
    if offset:
        order_params["offset"] = offset

    order_response = request_clover(orders_url, order_params)

    if order_number and order_response.status_code == 404:
        raise ValueError(f"Order {order_number} not found in Clover.")
    elif order_response.status_code != 200:
        order_response.raise_for_status()

    return order_response.json()


def _customer_cache_key(id: str) -> str:
    return f"CLOVER/CLOVER_CUSTOMER_{id}"


def request_clover_customer(id: str):
    data = cache.get(_customer_cache_key(id), None)
    if data:
        return data
    customers_url = path.join(
        settings.CLOVER_INTEGRATION_API,
        "merchants",
        settings.CLOVER_MERCHANT_ID,
        "customers",
        id,
    )
    params = {"expand": "addresses,emailAddresses,phoneNumbers"}
    response = request_clover(customers_url, params)
    if id and response.status_code == 404:
        raise ValueError(f"Customer {id} not found in Clover.")
    elif response.status_code != 200:
        response.raise_for_status()

    data = response.json()
    cache.set(_customer_cache_key(id), data)
    return data


def request_clover_customer_list(ids: Sequence[str]):
    customers_url = path.join(
        settings.CLOVER_INTEGRATION_API,
        "merchants",
        settings.CLOVER_MERCHANT_ID,
        "customers",
    )
    customer_query_param_list = "','".join(ids)
    filter_str = f"id in ('{customer_query_param_list}')"
    params = {"filter": filter_str, "expand": "addresses,emailAddresses,phoneNumbers"}
    response = request_clover(customers_url, params)
    if response.status_code != 200:
        response.raise_for_status()

    customer_data = {c["id"]: c for c in response.json()["elements"]}
    for k, data in customer_data.items():
        cache.set(_customer_cache_key(k), data)
    return customer_data


def is_clover_delivery_item(item_name):
    return (
        "Shipping and Handling" in item_name
        or "Delivery" in item_name
        or "Shipping Fee" in item_name
    )


def is_clover_delivery(order_info):
    if (
        "lineItems" not in order_info
        or "elements" not in order_info["lineItems"]
        or not order_info["lineItems"]["elements"]
    ):
        return False
    for item in order_info["lineItems"]["elements"]:
        if is_clover_delivery_item(item["name"]):
            return True
    return False
