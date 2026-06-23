#!/usr/bin/env python3

from __future__ import annotations

import warnings


def filter_known_runtime_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r"The value of the smallest subnormal for <class 'numpy\.float(32|64)'> type is zero\.",
        category=UserWarning,
        module=r"numpy\._core\.getlimits",
    )
