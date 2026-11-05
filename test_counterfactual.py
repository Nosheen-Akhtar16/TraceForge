import json

import pytest
from fastapi import HTTPException

import main


def test_compare_conditions_identifies_same_and_different_values():
    conditions_a = {
        "browser": "Chrome",
        "network": "slow",
        "app_state": "logged_out",
    }

    conditions_b = {
        "browser": "Chrome",
        "network": "fast",
        "app_state": "logged_out",
    }

    result = main.compare_conditions(
        conditions_a,
        conditions_b,
    )

    assert result["same"] == {
        "app_state": "logged_out",
        "browser": "Chrome",
    }

    assert result["different"] == {
        "network": {
            "attempt_a": "slow",
            "attempt_b": "fast",
        }
    }

    assert result["unknown"] == []


def test_compare_conditions_marks_missing_values_unknown():
    conditions_a = {
        "browser": "Chrome",
        "network": "slow",
    }

    conditions_b = {
        "browser": "Chrome",
        "test_data": "user_A",
    }

    result = main.compare_conditions(
        conditions_a,
        conditions_b,
    )

    assert result["same"] == {
        "browser": "Chrome",
    }

    assert result["different"] == {}

    assert result["unknown"] == [
        {
            "condition": "network",
            "attempt_a": "slow",
            "attempt_b": None,
        },
        {
            "condition": "test_data",
            "attempt_a": None,
            "attempt_b": "user_A",
        },
    ]


def test_compare_conditions_treats_none_as_unknown():
    conditions_a = {
        "network": None,
    }

    conditions_b = {
        "network": "slow",
    }

    result = main.compare_conditions(
        conditions_a,
        conditions_b,
    )

    assert result["unknown"] == [
        {
            "condition": "network",
            "attempt_a": None,
            "attempt_b": "slow",
        }
    ]


def test_compare_conditions_includes_causality_warning():
    result = main.compare_conditions(
        {"network": "slow"},
        {"network": "fast"},
    )

    assert "do not prove the root cause" in (
        result["causality_warning"]
    )