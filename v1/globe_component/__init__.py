import os

import streamlit.components.v1 as components

_FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")
os.makedirs(os.path.join(_FRONTEND, "assets"), exist_ok=True)

_component = components.declare_component("geolite_globe", path=_FRONTEND)


def globes(spec: dict, key: str, default=None):
    return _component(spec=spec, key=key, default=default)
