# -*- coding: utf-8 -*-
import click
import logging
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

from operator import itemgetter
import json

def load_data(filepath="../data/raw/data.json", top_n=0):
    """
    Returns:
      timestamps : list[datetime]
      bids       : list[float]
      asks       : list[float]
    """
    with open(filepath, "r") as f:
        raw = json.load(f)
    ticks0 = raw[0]["ticks"]
    ticks1 = raw[1]["ticks"]
    # extract
    raw_ts = list(map(itemgetter(0), ticks0))
    timestamps = list(map(lambda ts: ts / 1e6, raw_ts))

    bids = list(map(itemgetter(1), ticks0))
    asks = list(map(itemgetter(1), ticks1))
    # optional: trim to top_n
    if top_n > 0:
        timestamps, bids, asks = (l[:top_n] for l in (timestamps, bids, asks))
    return timestamps, bids, asks