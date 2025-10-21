import argparse
import os
import yaml


def _deep_update(base: dict, override: dict) -> dict:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_config() -> dict:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile", choices=["tile", "carpet", "outdoors"], default=None)
    parser.add_argument("--config", default=None)
    args, _ = parser.parse_known_args()

    # Resolve repo root relative to this file
    root = os.path.dirname(os.path.dirname(__file__))
    default_path = os.path.join(root, "config", "default.yaml")

    with open(default_path, "r") as f:
        data = yaml.safe_load(f) or {}

    if args.profile:
        prof_path = os.path.join(root, "config", "profiles", f"{args.profile}.yaml")
        if os.path.exists(prof_path):
            with open(prof_path, "r") as pf:
                prof = yaml.safe_load(pf) or {}
            data = _deep_update(data, prof)

    if args.config and os.path.exists(args.config):
        with open(args.config, "r") as cf:
            user = yaml.safe_load(cf) or {}
        data = _deep_update(data, user)

    # Normalize defaults and ensure all sections exist; keep original keys
    data.setdefault("serial", {})
    data["serial"].setdefault("port", "/dev/ttyACM0")
    data["serial"].setdefault("baud", 115200)
    data["serial"].setdefault("timeout_ms", 120)
    data.setdefault("loop_sleep_s", 0.01)
    data.setdefault("pairing_seconds", 5)
    data.setdefault("thresholds_cm", {})
    data.setdefault("sweep", {})
    data.setdefault("cadence_ms", {})
    data.setdefault("pwm", {})
    data.setdefault("watchdog", {})
    data.setdefault("logging", {})
    return data


