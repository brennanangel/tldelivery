import shopify
import json

from typing import Sequence, Optional, Tuple

import dateutil.parser

from django.conf import settings
from .models import Shift

# from django.core.cache import cache


_SHIFT_FOR_ORDERS_QUERY = """
{{
  orders(query: "{query}", first: 100) {{
    edges {{
      node {{
        name
        customAttributes {{
          key
          value
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

CACHE = {}


def parse_shopify_delivery_time(order) -> Tuple[str, Optional[Shift]]:
    name = order["name"]
    if name.startswith("#"):
        name = name[1:]
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
        return (name, None)

    try:
        shift = Shift.objects.get(date=date.isoformat(), time=time)
        return (name, shift)
    except Shift.DoesNotExist:
        print(f"DOES NOT EXIST: {date} {time}")
        # probably want to log/error
        return (name, None)


def _format_order_number_query(order_names: Sequence[str]) -> str:
    return " OR ".join([f"name:{n}" for n in order_names])


def get_shifts_from_shopify(order_names: Sequence[str]):
    unknown = [o for o in order_names if o not in CACHE]
    if unknown:
        with shopify.Session.temp(
            settings.SHOPIFY_APP_URL,
            settings.SHOPIFY_API_VERSION,
            settings.SHOPIFY_APP_SECRET,
        ):
            response = json.loads(
                shopify.GraphQL().execute(
                    _SHIFT_FOR_ORDERS_QUERY.format(
                        query=_format_order_number_query(unknown)
                    )
                )
            )
            data = response["data"]
            orders = [n["node"] for n in data["orders"]["edges"]]
            for o in orders:
                name, shift = parse_shopify_delivery_time(o)

                CACHE[name] = shift

    return {o: CACHE.get(o, None) for o in order_names}
