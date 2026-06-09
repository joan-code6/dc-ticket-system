import json
import os
from typing import Dict, Any, Optional, List

CONFIG_PATH = "bot/config.json"

DEFAULT_CONFIG = {
    "categories": {},
    "panel_title": "Support Tickets",
    "panel_description": ["Click the button below to create a ticket."],
    "stats_channel_id": None,
    "stats_message_id": None,
    "stats_leaderboard_message_id": None,
    "stats_claims_leaderboard_message_id": None,
    "stats_messages_leaderboard_message_id": None,
    "stats_total_messages_leaderboard_message_id": None,
    "archive_channel_id": None,
    "staff_role_id": None,
    "dashboard_channel_id": None,
    "dashboard_message_id": None,
    "transcript_channel_id": None,
    "ticket_utilization_channel_id": None,
    "ticket_utilization_message_id": None,
    "ticket_utilization_max_tickets": 40,
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

    def replace_config(self, new_config: Dict[str, Any]):
        self._save(new_config)
        self._config = new_config

    def get_category(self, name: str) -> Optional[Dict[str, Any]]:
        return self.config.get("categories", {}).get(name)

    def get_categories(self) -> Dict[str, Any]:
        return self.config.get("categories", {})

    def set_category(
        self,
        name: str,
        discord_category_id: int,
        role_name: str,
        questions: Optional[List[str]] = None,
    ):
        cfg = self.config
        if "categories" not in cfg:
            cfg["categories"] = {}
        cfg["categories"][name] = {
            "discord_category_id": discord_category_id,
            "role_name": role_name,
            "questions": questions or [],
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

    def set_stats_channel(
        self,
        channel_id: int,
        message_id: int,
        leaderboard_message_id: int = None,
        claims_leaderboard_message_id: int = None,
        messages_leaderboard_message_id: int = None,
        total_messages_leaderboard_message_id: int = None,
    ):
        cfg = self.config
        cfg["stats_channel_id"] = channel_id
        cfg["stats_message_id"] = message_id
        cfg["stats_leaderboard_message_id"] = leaderboard_message_id
        cfg["stats_claims_leaderboard_message_id"] = claims_leaderboard_message_id
        cfg["stats_messages_leaderboard_message_id"] = messages_leaderboard_message_id
        cfg["stats_total_messages_leaderboard_message_id"] = (
            total_messages_leaderboard_message_id
        )
        self._save(cfg)
        self._config = cfg

    def get_stats_channel(self) -> Optional[int]:
        return self.config.get("stats_channel_id")

    def get_stats_message(self) -> Optional[int]:
        return self.config.get("stats_message_id")

    def get_stats_leaderboard_message(self) -> Optional[int]:
        return self.config.get("stats_leaderboard_message_id")

    def get_stats_claims_leaderboard_message(self) -> Optional[int]:
        return self.config.get("stats_claims_leaderboard_message_id")

    def get_stats_messages_leaderboard_message(self) -> Optional[int]:
        return self.config.get("stats_messages_leaderboard_message_id")

    def get_stats_total_messages_leaderboard_message(self) -> Optional[int]:
        return self.config.get("stats_total_messages_leaderboard_message_id")

    def get_archive_channel(self) -> Optional[int]:
        return self.config.get("archive_channel_id")

    def set_archive_channel(self, channel_id: int):
        cfg = self.config
        cfg["archive_channel_id"] = channel_id
        self._save(cfg)
        self._config = cfg

    def delete_category(self, name: str):
        cfg = self.config
        if name in cfg.get("categories", {}):
            del cfg["categories"][name]
            self._save(cfg)
            self._config = cfg

    def get_staff_role(self) -> Optional[int]:
        return self.config.get("staff_role_id")

    def set_staff_role(self, role_id: int):
        cfg = self.config
        cfg["staff_role_id"] = role_id
        self._save(cfg)
        self._config = cfg

    def get_panel_title(self) -> str:
        return self.config.get("panel_title", "Support Tickets")

    def get_panel_description(self) -> str:
        desc = self.config.get(
            "panel_description", ["Click the button below to create a ticket."]
        )
        if isinstance(desc, list):
            return "\n".join(desc)
        return desc

    def set_panel_text(self, title: str, description: str):
        cfg = self.config
        cfg["panel_title"] = title
        cfg["panel_description"] = description.split("\n") if description else []
        self._save(cfg)
        self._config = cfg

    def get_dashboard_channel(self) -> Optional[int]:
        return self.config.get("dashboard_channel_id")

    def get_dashboard_message(self) -> Optional[int]:
        return self.config.get("dashboard_message_id")

    def set_dashboard(self, channel_id: int, message_id: int):
        cfg = self.config
        cfg["dashboard_channel_id"] = channel_id
        cfg["dashboard_message_id"] = message_id
        self._save(cfg)
        self._config = cfg

    def get_transcript_channel(self) -> Optional[int]:
        return self.config.get("transcript_channel_id")

    def set_transcript_channel(self, channel_id: int):
        cfg = self.config
        cfg["transcript_channel_id"] = channel_id
        self._save(cfg)
        self._config = cfg

    def get_ticket_utilization_channel(self) -> Optional[int]:
        return self.config.get("ticket_utilization_channel_id")

    def get_ticket_utilization_message(self) -> Optional[int]:
        return self.config.get("ticket_utilization_message_id")

    def get_ticket_utilization_max_tickets(self) -> int:
        return self.config.get("ticket_utilization_max_tickets", 40)

    def set_ticket_utilization(
        self, channel_id: int, message_id: int, max_tickets: int
    ):
        cfg = self.config
        cfg["ticket_utilization_channel_id"] = channel_id
        cfg["ticket_utilization_message_id"] = message_id
        cfg["ticket_utilization_max_tickets"] = max_tickets
        self._save(cfg)
        self._config = cfg
