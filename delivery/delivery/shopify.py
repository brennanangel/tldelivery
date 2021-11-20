import shopify
import json
import os
from dataclasses import dataclass

from typing import Sequence, Optional, Tuple, Mapping, Dict

import dateutil.parser

from django.conf import settings
from django.core.cache import cache

from .models import Shift


@dataclass(frozen=True)
class ShopifyOrderInfo:
    name: str
    online_id: str
    shift: Optional[Shift]
    phone: Optional[str]  # temp due to SkuIQ not syncing customer number


_SHIFT_FOR_ORDERS_QUERY = """
{{
  orders(query: "{query}", first: 100) {{
    edges {{
      node {{
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
        with shopify.Session.temp(
            settings.SHOPIFY_APP_URL,
            settings.SHOPIFY_API_VERSION,
            settings.SHOPIFY_APP_SECRET,
        ):
            response = json.loads(
                shopify.GraphQL().execute(
                    _SHIFT_FOR_ORDERS_QUERY.format(
                        query=_format_order_name_query(unknown)
                    )
                )
            )
            data = response["data"]
            orders = [n["node"] for n in data["orders"]["edges"]]
            for o in orders:
                name = o["name"]
                if name.startswith("#"):
                    name = name[1:]
                oid = os.path.basename(o["id"])
                shift = _parse_shopify_delivery_time(o)
                phone = _parse_phone_number(o)
                CACHE_INFO_BY_NAME[name] = ShopifyOrderInfo(name, oid, shift, phone)

    return {o: CACHE_INFO_BY_NAME.get(o, None) for o in order_names}
