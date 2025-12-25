"""Configuration management for OpenList2STRM v1.1.0"""

import os
import uuid
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


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
    mode: str = "path"  # "path" or "direct_link"
    output_path: str = "/strm"  # Local STRM output path


@dataclass
class QoSConfig:
    """QoS rate limiting configuration"""
    qps: float = 5.0
    max_concurrent: int = 3
    interval: int = 200  # milliseconds
    threading_mode: str = "multi"  # "single" or "multi"
    thread_pool_size: int = 4
    rate_limit: int = 100  # requests per minute


@dataclass
class TaskConfig:
    """Individual scheduled task configuration"""
    id: str = ""
    name: str = ""
    folder: str = ""
    cron: str = "0 2 * * *"  # Kept for backward compatibility and internal use
    schedule_type: str = "cron"  # "cron", "interval", "daily", "once"
    schedule_value: str = ""  # e.g., "30" (minutes) or "04:00" (time)
    enabled: bool = True
    paused: bool = False
    one_time: bool = False
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = f"task_{uuid.uuid4().hex[:8]}"
        
        # If schedule_type is not set but cron is, try to infer (basic migration)
        if self.schedule_type == "cron" and not self.schedule_value:
            self.schedule_value = self.cron
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "folder": self.folder,
            "cron": self.cron,
            "schedule_type": self.schedule_type,
            "schedule_value": self.schedule_value,
            "enabled": self.enabled,
            "paused": self.paused,
            "one_time": self.one_time,
            "last_run": self.last_run,
            "next_run": self.next_run,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskConfig":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            folder=data.get("folder", ""),
            cron=data.get("cron", "0 2 * * *"),
            schedule_type=data.get("schedule_type", "cron"),
            schedule_value=data.get("schedule_value", ""),
            enabled=data.get("enabled", True),
            paused=data.get("paused", False),
            one_time=data.get("one_time", False),
            last_run=data.get("last_run"),
            next_run=data.get("next_run"),
        )


@dataclass
class ScheduleConfig:
    """Schedule configuration (legacy + multi-task)"""
    enabled: bool = False
    cron: str = "0 4 * * 1"
    on_startup: bool = False
    tasks: List[TaskConfig] = field(default_factory=list)


@dataclass
class ScanConfig:
    """Scan mode configuration"""
    mode: str = "incremental"  # "incremental" or "full"
    data_source: str = "cache"  # "cache" or "realtime"


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
    chat_id: str = ""  # User/Chat ID for notifications
    allowed_users: List[int] = field(default_factory=list)
    notify: TelegramNotifyConfig = field(default_factory=TelegramNotifyConfig)


@dataclass
class EmbyConfig:
    """Emby notification configuration"""
    enabled: bool = False
    host: str = ""  # e.g., http://emby:8096
    api_key: str = ""
    library_id: str = ""  # Empty for all libraries
    notify_on_scan: bool = True


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
    scan: ScanConfig = field(default_factory=ScanConfig)
    incremental: IncrementalConfig = field(default_factory=IncrementalConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    emby: EmbyConfig = field(default_factory=EmbyConfig)
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
                mode=s.get("mode", config.strm.mode),
                output_path=s.get("output_path", config.strm.output_path),
            )
        
        # QoS config
        if "qos" in data:
            q = data["qos"]
            config.qos = QoSConfig(
                qps=q.get("qps", config.qos.qps),
                max_concurrent=q.get("max_concurrent", config.qos.max_concurrent),
                interval=q.get("interval", config.qos.interval),
                threading_mode=q.get("threading_mode", config.qos.threading_mode),
                thread_pool_size=q.get("thread_pool_size", config.qos.thread_pool_size),
                rate_limit=q.get("rate_limit", config.qos.rate_limit),
            )
        
        # Schedule config with multi-task support
        if "schedule" in data:
            sc = data["schedule"]
            tasks = []
            if "tasks" in sc:
                for t in sc["tasks"]:
                    tasks.append(TaskConfig.from_dict(t))
            config.schedule = ScheduleConfig(
                enabled=sc.get("enabled", config.schedule.enabled),
                cron=sc.get("cron", config.schedule.cron),
                on_startup=sc.get("on_startup", config.schedule.on_startup),
                tasks=tasks,
            )
        
        # Scan config
        if "scan" in data:
            sc = data["scan"]
            config.scan = ScanConfig(
                mode=sc.get("mode", config.scan.mode),
                data_source=sc.get("data_source", config.scan.data_source),
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
                chat_id=tg.get("chat_id", config.telegram.chat_id),
                allowed_users=tg.get("allowed_users", config.telegram.allowed_users),
                notify=notify,
            )
        
        # Emby config
        if "emby" in data:
            em = data["emby"]
            config.emby = EmbyConfig(
                enabled=em.get("enabled", config.emby.enabled),
                host=em.get("host", config.emby.host),
                api_key=em.get("api_key", config.emby.api_key),
                library_id=em.get("library_id", config.emby.library_id),
                notify_on_scan=em.get("notify_on_scan", config.emby.notify_on_scan),
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
                "mode": self.strm.mode,
                "output_path": self.strm.output_path,
            },
            "qos": {
                "qps": self.qos.qps,
                "max_concurrent": self.qos.max_concurrent,
                "interval": self.qos.interval,
                "threading_mode": self.qos.threading_mode,
                "thread_pool_size": self.qos.thread_pool_size,
                "rate_limit": self.qos.rate_limit,
            },
            "schedule": {
                "enabled": self.schedule.enabled,
                "cron": self.schedule.cron,
                "on_startup": self.schedule.on_startup,
                "tasks": [t.to_dict() for t in self.schedule.tasks],
            },
            "scan": {
                "mode": self.scan.mode,
                "data_source": self.scan.data_source,
            },
            "incremental": {
                "enabled": self.incremental.enabled,
                "check_method": self.incremental.check_method,
            },
            "telegram": {
                "enabled": self.telegram.enabled,
                "token": "***" if self.telegram.token else "",
                "chat_id": self.telegram.chat_id,
                "allowed_users": self.telegram.allowed_users,
                "notify": {
                    "on_scan_start": self.telegram.notify.on_scan_start,
                    "on_scan_complete": self.telegram.notify.on_scan_complete,
                    "on_error": self.telegram.notify.on_error,
                },
            },
            "emby": {
                "enabled": self.emby.enabled,
                "host": self.emby.host,
                "api_key": "***" if self.emby.api_key else "",
                "library_id": self.emby.library_id,
                "notify_on_scan": self.emby.notify_on_scan,
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
    
    def save(self, config_path: Optional[str] = None) -> bool:
        """Save configuration to file with improved permission handling"""
        if config_path is None:
            config_path = os.environ.get("CONFIG_PATH", "/config/config.yml")
        
        path = Path(config_path)
        directory = path.parent
        
        try:
            # Ensure directory exists
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
            
            # Check if directory is writable, try to fix if not
            if not os.access(directory, os.W_OK):
                try:
                    # Attempt to add write permission for the current user/group
                    # This might fail if app isn't running as root/owner
                    current_mode = directory.stat().st_mode
                    os.chmod(directory, current_mode | 0o200) 
                except Exception as e:
                    print(f"Warning: Cannot fix directory permissions for {directory}: {e}")
            
            # If file exists, check writability
            if path.exists() and not os.access(path, os.W_OK):
                try:
                    current_mode = path.stat().st_mode
                    os.chmod(path, current_mode | 0o200)
                except Exception as e:
                    print(f"Warning: Cannot fix file permissions for {path}: {e}")

            # Build save dict (with full credentials)
            save_data = {
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
                    "mode": self.strm.mode,
                    "output_path": self.strm.output_path,
                },
                "qos": {
                    "qps": self.qos.qps,
                    "max_concurrent": self.qos.max_concurrent,
                    "interval": self.qos.interval,
                    "threading_mode": self.qos.threading_mode,
                    "thread_pool_size": self.qos.thread_pool_size,
                    "rate_limit": self.qos.rate_limit,
                },
                "schedule": {
                    "enabled": self.schedule.enabled,
                    "cron": self.schedule.cron,
                    "on_startup": self.schedule.on_startup,
                    "tasks": [t.to_dict() for t in self.schedule.tasks],
                },
                "scan": {
                    "mode": self.scan.mode,
                    "data_source": self.scan.data_source,
                },
                "incremental": {
                    "enabled": self.incremental.enabled,
                    "check_method": self.incremental.check_method,
                },
                "telegram": {
                    "enabled": self.telegram.enabled,
                    "token": self.telegram.token,
                    "chat_id": self.telegram.chat_id,
                    "allowed_users": self.telegram.allowed_users,
                    "notify": {
                        "on_scan_start": self.telegram.notify.on_scan_start,
                        "on_scan_complete": self.telegram.notify.on_scan_complete,
                        "on_error": self.telegram.notify.on_error,
                    },
                },
                "emby": {
                    "enabled": self.emby.enabled,
                    "host": self.emby.host,
                    "api_key": self.emby.api_key,
                    "library_id": self.emby.library_id,
                    "notify_on_scan": self.emby.notify_on_scan,
                },
                "web": {
                    "enabled": self.web.enabled,
                    "port": self.web.port,
                    "auth": {
                        "enabled": self.web.auth.enabled,
                        "username": self.web.auth.username,
                        "password": self.web.auth.password,
                        "api_token": self.web.auth.api_token,
                    },
                },
                "logging": {
                    "level": self.logging.level,
                    "retention_days": self.logging.retention_days,
                    "colorize": self.logging.colorize,
                },
            }
            
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(save_data, f, default_flow_style=False, allow_unicode=True)
            
            return True
        except Exception as e:
            error_msg = f"Failed to save config to {config_path}: {str(e)}"
            print(error_msg)
            # Re-raise or keep returning False? Let's return False and let the API handle the message
            return False


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


def update_config(updates: Dict[str, Any]) -> Config:
    """Update and save configuration"""
    global _config
    if _config is None:
        _config = Config.load()
    
    # Apply updates to current config
    new_config = Config.from_dict({**_config.to_dict(), **updates})
    new_config.save()
    _config = new_config
    return _config
