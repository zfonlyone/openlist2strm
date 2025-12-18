"""Configuration management for OpenList2STRM"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class OpenListConfig:
    """OpenList API configuration"""
    host: str = "http://openlist:5244"
    token: str = ""
    timeout: int = 30


@dataclass
class PathsConfig:
    """Path configuration"""
    source: List[str] = field(default_factory=lambda: ["/115"])
    output: str = "/strm"


@dataclass
class StrmConfig:
    """STRM file configuration"""
    extensions: List[str] = field(default_factory=lambda: [
        ".mp4", ".mkv", ".avi", ".ts", ".wmv", ".rmvb", ".mov", ".flv", ".m2ts", ".webm"
    ])
    keep_structure: bool = True
    url_encode: bool = True


@dataclass
class QoSConfig:
    """QoS rate limiting configuration"""
    qps: float = 5.0
    max_concurrent: int = 3
    interval: int = 200  # milliseconds


@dataclass
class ScheduleConfig:
    """Schedule configuration"""
    enabled: bool = True
    cron: str = "0 2 * * *"
    on_startup: bool = False


@dataclass
class IncrementalConfig:
    """Incremental update configuration"""
    enabled: bool = True
    check_method: str = "mtime"  # mtime | size | both


@dataclass
class TelegramNotifyConfig:
    """Telegram notification settings"""
    on_scan_start: bool = True
    on_scan_complete: bool = True
    on_error: bool = True


@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    enabled: bool = False
    token: str = ""
    allowed_users: List[int] = field(default_factory=list)
    notify: TelegramNotifyConfig = field(default_factory=TelegramNotifyConfig)


@dataclass
class WebAuthConfig:
    """Web authentication configuration"""
    enabled: bool = True  # Auth enabled by default
    username: str = "admin"
    password: str = ""  # Password hash (empty = needs setup)
    api_token: str = ""  # API token for programmatic access


@dataclass
class WebConfig:
    """Web interface configuration"""
    enabled: bool = True
    port: int = 9527
    auth: WebAuthConfig = field(default_factory=WebAuthConfig)


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    retention_days: int = 7
    colorize: bool = True


@dataclass
class Config:
    """Main configuration class"""
    openlist: OpenListConfig = field(default_factory=OpenListConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    path_mapping: Dict[str, str] = field(default_factory=dict)
    strm: StrmConfig = field(default_factory=StrmConfig)
    qos: QoSConfig = field(default_factory=QoSConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    incremental: IncrementalConfig = field(default_factory=IncrementalConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    web: WebConfig = field(default_factory=WebConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create config from dictionary"""
        config = cls()
        
        # OpenList config
        if "openlist" in data:
            ol = data["openlist"]
            config.openlist = OpenListConfig(
                host=ol.get("host", config.openlist.host),
                token=ol.get("token", config.openlist.token),
                timeout=ol.get("timeout", config.openlist.timeout),
            )
        
        # Paths config
        if "paths" in data:
            p = data["paths"]
            config.paths = PathsConfig(
                source=p.get("source", config.paths.source),
                output=p.get("output", config.paths.output),
            )
        
        # Path mapping
        if "path_mapping" in data:
            config.path_mapping = data["path_mapping"]
        
        # STRM config
        if "strm" in data:
            s = data["strm"]
            config.strm = StrmConfig(
                extensions=s.get("extensions", config.strm.extensions),
                keep_structure=s.get("keep_structure", config.strm.keep_structure),
                url_encode=s.get("url_encode", config.strm.url_encode),
            )
        
        # QoS config
        if "qos" in data:
            q = data["qos"]
            config.qos = QoSConfig(
                qps=q.get("qps", config.qos.qps),
                max_concurrent=q.get("max_concurrent", config.qos.max_concurrent),
                interval=q.get("interval", config.qos.interval),
            )
        
        # Schedule config
        if "schedule" in data:
            sc = data["schedule"]
            config.schedule = ScheduleConfig(
                enabled=sc.get("enabled", config.schedule.enabled),
                cron=sc.get("cron", config.schedule.cron),
                on_startup=sc.get("on_startup", config.schedule.on_startup),
            )
        
        # Incremental config
        if "incremental" in data:
            inc = data["incremental"]
            config.incremental = IncrementalConfig(
                enabled=inc.get("enabled", config.incremental.enabled),
                check_method=inc.get("check_method", config.incremental.check_method),
            )
        
        # Telegram config
        if "telegram" in data:
            tg = data["telegram"]
            notify_data = tg.get("notify", {})
            notify = TelegramNotifyConfig(
                on_scan_start=notify_data.get("on_scan_start", True),
                on_scan_complete=notify_data.get("on_scan_complete", True),
                on_error=notify_data.get("on_error", True),
            )
            config.telegram = TelegramConfig(
                enabled=tg.get("enabled", config.telegram.enabled),
                token=tg.get("token", config.telegram.token),
                allowed_users=tg.get("allowed_users", config.telegram.allowed_users),
                notify=notify,
            )
        
        # Web config
        if "web" in data:
            w = data["web"]
            auth_data = w.get("auth", {})
            auth = WebAuthConfig(
                enabled=auth_data.get("enabled", True),
                username=auth_data.get("username", "admin"),
                password=auth_data.get("password", ""),
                api_token=auth_data.get("api_token", ""),
            )
            config.web = WebConfig(
                enabled=w.get("enabled", config.web.enabled),
                port=w.get("port", config.web.port),
                auth=auth,
            )
        
        # Logging config
        if "logging" in data:
            log = data["logging"]
            config.logging = LoggingConfig(
                level=log.get("level", config.logging.level),
                retention_days=log.get("retention_days", config.logging.retention_days),
                colorize=log.get("colorize", config.logging.colorize),
            )
        
        return config
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from file"""
        if config_path is None:
            config_path = os.environ.get("CONFIG_PATH", "/config/config.yml")
        
        path = Path(config_path)
        if not path.exists():
            # Try alternative paths
            alt_paths = [
                Path("/config/config.yml"),
                Path("/config/config.yaml"),
                Path("config/config.yml"),
                Path("config.yml"),
            ]
            for alt in alt_paths:
                if alt.exists():
                    path = alt
                    break
            else:
                # Return default config if no file found
                return cls()
        
        # Try to load config with error handling for encoding issues
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except UnicodeDecodeError:
            # Try with different encoding or ignore errors
            print(f"Warning: Config file has encoding issues, trying with error handling")
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse config file: {e}")
            return cls()
        
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "openlist": {
                "host": self.openlist.host,
                "token": self.openlist.token,
                "timeout": self.openlist.timeout,
            },
            "paths": {
                "source": self.paths.source,
                "output": self.paths.output,
            },
            "path_mapping": self.path_mapping,
            "strm": {
                "extensions": self.strm.extensions,
                "keep_structure": self.strm.keep_structure,
                "url_encode": self.strm.url_encode,
            },
            "qos": {
                "qps": self.qos.qps,
                "max_concurrent": self.qos.max_concurrent,
                "interval": self.qos.interval,
            },
            "schedule": {
                "enabled": self.schedule.enabled,
                "cron": self.schedule.cron,
                "on_startup": self.schedule.on_startup,
            },
            "incremental": {
                "enabled": self.incremental.enabled,
                "check_method": self.incremental.check_method,
            },
            "telegram": {
                "enabled": self.telegram.enabled,
                "token": "***" if self.telegram.token else "",
                "allowed_users": self.telegram.allowed_users,
                "notify": {
                    "on_scan_start": self.telegram.notify.on_scan_start,
                    "on_scan_complete": self.telegram.notify.on_scan_complete,
                    "on_error": self.telegram.notify.on_error,
                },
            },
            "web": {
                "enabled": self.web.enabled,
                "port": self.web.port,
                "auth": {
                    "enabled": self.web.auth.enabled,
                    "username": self.web.auth.username,
                },
            },
            "logging": {
                "level": self.logging.level,
                "retention_days": self.logging.retention_days,
                "colorize": self.logging.colorize,
            },
        }


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config() -> Config:
    """Reload configuration from file"""
    global _config
    _config = Config.load()
    return _config
