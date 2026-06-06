import json
import os
from typing import Dict, Any, Optional, List

CONFIG_PATH = "bot/config.json"

DEFAULT_CONFIG = {
    "categories": {},
    "stats_channel_id": None,
    "stats_message_id": None,
    "stats_leaderboard_message_id": None
}


class ConfigManager:
    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self._config = None
        self._ensure_exists()

    def _ensure_exists(self):
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)

    def _load(self) -> Dict[str, Any]:
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, config: Dict[str, Any]):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    @property
    def config(self) -> Dict[str, Any]:
        if self._config is None:
            self._config = self._load()
        return self._config

    def reload(self):
        self._config = self._load()

    def get_category(self, name: str) -> Optional[Dict[str, Any]]:
        return self.config.get("categories", {}).get(name)

    def get_categories(self) -> Dict[str, Any]:
        return self.config.get("categories", {})

    def set_category(self, name: str, discord_category_id: int, role_name: str, questions: Optional[List[str]] = None):
        cfg = self.config
        if "categories" not in cfg:
            cfg["categories"] = {}
        cfg["categories"][name] = {
            "discord_category_id": discord_category_id,
            "role_name": role_name,
            "questions": questions or []
        }
        self._save(cfg)
        self._config = cfg

    def set_questions(self, category: str, questions: List[str]):
        cfg = self.config
        if category not in cfg.get("categories", {}):
            raise ValueError(f"Category '{category}' does not exist.")
        cfg["categories"][category]["questions"] = questions
        self._save(cfg)
        self._config = cfg

    def set_stats_channel(self, channel_id: int, message_id: int, leaderboard_message_id: int = None):
        cfg = self.config
        cfg["stats_channel_id"] = channel_id
        cfg["stats_message_id"] = message_id
        cfg["stats_leaderboard_message_id"] = leaderboard_message_id
        self._save(cfg)
        self._config = cfg

    def get_stats_channel(self) -> Optional[int]:
        return self.config.get("stats_channel_id")

    def get_stats_message(self) -> Optional[int]:
        return self.config.get("stats_message_id")

    def get_stats_leaderboard_message(self) -> Optional[int]:
        return self.config.get("stats_leaderboard_message_id")

    def delete_category(self, name: str):
        cfg = self.config
        if name in cfg.get("categories", {}):
            del cfg["categories"][name]
            self._save(cfg)
            self._config = cfg
