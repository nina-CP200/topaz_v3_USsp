from __future__ import annotations
import json
import os
from fastapi import APIRouter
from pydantic import BaseModel
from backend.routers.common import PROJECT_ROOT

router = APIRouter()

CONFIG_FILE = os.path.join(PROJECT_ROOT, "data/raw/slack_configs.json")
MASKED_TOKEN = "********"


class SlackConfigItem(BaseModel):
    name: str
    token: str
    channel: str


def _load() -> list[dict]:
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(configs: list[dict]):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(configs, f, indent=2, ensure_ascii=False)


@router.get("/slack")
def list_configs():
    configs = []
    for c in _load():
        configs.append({**c, "token": MASKED_TOKEN if c.get("token") else ""})
    return {"configs": configs}


@router.put("/slack")
def save_configs(data: list[SlackConfigItem]):
    old_by_name = {c.get("name"): c for c in _load()}
    configs = []
    for item in data:
        token = item.token
        old = old_by_name.get(item.name)
        if token == MASKED_TOKEN and old:
            token = old.get("token", "")
        configs.append({"name": item.name, "token": token, "channel": item.channel})
    _save(configs)
    return {"message": f"已保存 {len(configs)} 个 Slack 配置"}
