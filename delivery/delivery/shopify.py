import shopify
import json
import os
from dataclasses import dataclass

from typing import Sequence, Optional, Mapping, Dict

import dateutil.parser

from django.conf import settings
from django.core.cache import cache

from .models import Shift


@dataclass(frozen=True)
class ShopifyOrderInfo:
    name: str
    online_id: str
    created_at: str
    shift: Optional[Shift]
    phone: Optional[str]  # temp due to SkuIQ not syncing customer number
    first_name: Optional[str]  # temp due to SkuIQ not syncing customer number
    last_name: Optional[str]  # temp due to SkuIQ not syncing customer number


_SHIFT_FOR_ORDERS_QUERY = """
{{
  orders(query: "{query}", first: {chunk_size} {cursor}) {{
    pageInfo {{
        hasNextPage
    }}
    edges {{
      cursor
      node {{
        createdAt
        name
        id
        customAttributes {{
          key
          value
        }}
        shippingAddress {{
            phone
        }}
        customer {{
            firstName
            lastName
            phone
            defaultAddress {{
                phone
            }}
        }}
      }}
    }}
  }}
}}
"""


_TIME_TO_SHIFT_MAP = {
    "3:00 PM - 7:00 PM": "PM",
    "03:00 PM - 07:00 PM": "PM",
    "9:30 AM - 2:00 PM": "AM",
}

CACHE_INFO_BY_NAME: Dict[str, ShopifyOrderInfo] = {}


def _get_orders_for_query(query: str, chunk_size: int = 100) -> Sequence[Dict]:
    orders = []
    with shopify.Session.temp(
        settings.SHOPIFY_APP_URL,
        settings.SHOPIFY_API_VERSION,
        settings.SHOPIFY_APP_SECRET,
    ):
        cursor = None
        while True:
            response = json.loads(
                shopify.GraphQL().execute(
                    _SHIFT_FOR_ORDERS_QUERY.format(
                        query=query,
                        chunk_size=chunk_size,
                        cursor=f', cursor: "{cursor}"' if cursor else "",
                    )
                )
            )
            data = response["data"]
            orders.extend([n["node"] for n in data["orders"]["edges"]])
            if not data["orders"]["pageInfo"]["hasNextPage"]:
                break
            cursor = data["orders"]["edges"][-1]["cursor"]
    return orders


def _parse_shopify_delivery_time(order) -> Optional[Shift]:
    try:
        date = next(
            dateutil.parser.parse(o["value"]).date()
            for o in order["customAttributes"]
            if o["key"] == "Delivery-Date"
        )
        time = next(
            _TIME_TO_SHIFT_MAP.get(o["value"])
            for o in order["customAttributes"]
            if o["key"] == "Delivery-Time"
        )
    except (StopIteration, KeyError):
        return None

    try:
        shift = Shift.objects.get(date=date.isoformat(), time=time)
        return shift
    except Shift.DoesNotExist:
        print(f"DOES NOT EXIST: {date} {time}")
        # probably want to log/error
        return None


def _parse_phone_number(order) -> Optional[str]:
    if "shippingAddress" in order and order["shippingAddress"]["phone"]:
        return order["shippingAddress"]["phone"]
    customer = order.get("customer", None)
    if customer is None:
        return None
    if customer["phone"]:
        return customer["phone"]
    if "defaultAddress" in customer and customer["defaultAddress"]["phone"]:
        return customer["defaultAddress"]["phone"]
    return None


def _format_order_name_query(order_names: Sequence[str]) -> str:
    return " OR ".join([f"name:{n}" for n in order_names])


def get_data_from_shopify_by_name(
    order_names: Sequence[str],
) -> Mapping[str, Optional[ShopifyOrderInfo]]:
    unknown = [o for o in order_names if o not in CACHE_INFO_BY_NAME]
    if unknown:
        orders = _get_orders_for_query(_format_order_name_query(unknown))
        for o in orders:
            name = o["name"]
            if name.startswith("#"):
                name = name[1:]
            oid = os.path.basename(o["id"])
            created_at = o["createdAt"]
            first_name = o["customer"]["firstName"] if "customer" in o else None
            last_name = o["customer"]["lastName"] if "customer" in o else None
            shift = _parse_shopify_delivery_time(o)
            phone = _parse_phone_number(o)
            CACHE_INFO_BY_NAME[name] = ShopifyOrderInfo(
                name, oid, created_at, shift, phone, first_name, last_name
            )

    return {o: CACHE_INFO_BY_NAME.get(o, None) for o in order_names}


def get_data_by_time_range(delivery_only: bool = False) -> Sequence[ShopifyOrderInfo]:
    orders = []
    for o in _get_orders_for_query("updated_at:>2021-11-17"):
        if delivery_only:
            try:
                next(
                    a
                    for a in o["customAttributes"]
                    if a["key"] == "Checkout-Method" and a["value"] == "delivery"
                )
            except (StopIteration, KeyError):
                continue
        name = o["name"]
        if name.startswith("#"):
            name = name[1:]
        oid = os.path.basename(o["id"])
        created_at = o["createdAt"]
        first_name = o["customer"]["firstName"] if "customer" in o else None
        last_name = o["customer"]["lastName"] if "customer" in o else None
        shift = _parse_shopify_delivery_time(o)
        phone = _parse_phone_number(o)
        orders.append(
            ShopifyOrderInfo(name, oid, created_at, shift, phone, first_name, last_name)
        )
    return orders
