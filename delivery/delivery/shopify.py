import shopify
import json
import os
import datetime
from dataclasses import dataclass

from typing import Sequence, Optional, Mapping, Dict

import dateutil.parser

from django.conf import settings
from django.core.cache import cache

from delivery.delivery.constants import DeliveryTypes, DELIVERY_TYPE_COSTS

from .models import Shift


@dataclass(frozen=True)
class ShopifyOrderInfo:
    name: str
    online_id: str
    created_at: str
    shift: Optional[Shift]
    phone: str
    first_name: str
    last_name: str
    customer_first_name: str
    customer_last_name: str


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
            firstName
            lastName
            address1
            address2
            city
            zip
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


_ORDER_INFO_QUERY = """
{{
  order(id: "gid://shopify/Order/{oid}") {{
    createdAt
    name
    id
    customAttributes {{
        key
        value
    }}
    lineItems (first: 10){{
        edges {{
            node {{
                name
                quantity

            }}
        }}
    }}
    totalShippingPriceSet {{
        shopMoney {{
            amount
        }}
    }}
    note
    shippingAddress {{
        firstName
        lastName
        address1
        address2
        city
        zip
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
                        cursor=f', after: "{cursor}"' if cursor else "",
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


def _parse_phone_number(order) -> str:
    if "shippingAddress" in order and order["shippingAddress"]["phone"]:
        return order["shippingAddress"]["phone"]
    customer = order["customer"]
    if customer["phone"]:
        return customer["phone"]
    return customer["defaultAddress"]["phone"]


def _format_order_name_query(order_names: Sequence[str]) -> str:
    return " OR ".join([f"name:{n}" for n in order_names])


def _is_delivery_order(order_data) -> bool:
    try:
        next(
            a
            for a in order_data["customAttributes"]
            if a["key"] == "Checkout-Method" and a["value"] == "delivery"
        )
        return True
    except (StopIteration, KeyError):
        return False


def parse_order_info_from_data(order_data: Dict) -> ShopifyOrderInfo:
    name = order_data["name"]
    if name.startswith("#"):
        name = name[1:]
    online_id = os.path.basename(order_data["id"])
    created_at = order_data["createdAt"]
    shift = _parse_shopify_delivery_time(order_data)
    phone = _parse_phone_number(order_data)
    return ShopifyOrderInfo(
        name,
        online_id,
        created_at,
        shift,
        phone,
        first_name=order_data["shippingAddress"]["firstName"],
        last_name=order_data["shippingAddress"]["lastName"],
        customer_first_name=order_data["customer"]["firstName"],
        customer_last_name=order_data["customer"]["lastName"],
    )


def parse_delivery_type_from_data(order_data: Dict) -> Optional[DeliveryTypes]:
    shipping_cost = order_data["totalShippingPriceSet"]["shopMoney"]["amount"]
    try:
        shipping_cost = float(shipping_cost)
        if shipping_cost <= 0:
            return None
    except (TypeError, ValueError):
        return None

    return DELIVERY_TYPE_COSTS.get(shipping_cost * 100, DeliveryTypes.WHITE_GLOVE)


def get_data_from_shopify_by_name(
    order_names: Sequence[str], delivery_only: bool = False
) -> Mapping[str, Optional[ShopifyOrderInfo]]:
    unknown = [o for o in order_names if o not in CACHE_INFO_BY_NAME]
    if unknown:
        orders = _get_orders_for_query(_format_order_name_query(unknown))
        for o in orders:
            if delivery_only and not _is_delivery_order(o):
                continue
            info = parse_order_info_from_data(o)
            CACHE_INFO_BY_NAME[info.name] = info

    return {o: CACHE_INFO_BY_NAME.get(o, None) for o in order_names}


def get_data_by_time_range(
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
    delivery_only: bool = False,
) -> Sequence[ShopifyOrderInfo]:

    start_time = datetime.datetime.combine(start_date, datetime.datetime.min.time())
    date_filter = f"created_at:>{start_time.isoformat()}"
    if end_date:
        end_time = datetime.datetime.combine(end_date, datetime.datetime.max.time())
        date_filter += f" AND created_at:<{end_time.isoformat()}"
    orders = []
    for o in _get_orders_for_query(date_filter):
        if delivery_only and not _is_delivery_order(o):
            continue
        orders.append(parse_order_info_from_data(o))
    return orders


def get_data_by_id(online_id: str) -> Dict:
    with shopify.Session.temp(
        settings.SHOPIFY_APP_URL,
        settings.SHOPIFY_API_VERSION,
        settings.SHOPIFY_APP_SECRET,
    ):
        response = json.loads(
            shopify.GraphQL().execute(
                _ORDER_INFO_QUERY.format(
                    oid=online_id,
                )
            )
        )
    return response["data"]["order"]
