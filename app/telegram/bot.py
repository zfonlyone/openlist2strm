"""Telegram bot implementation"""

import asyncio
import logging
from typing import List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import get_config

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram bot for OpenList2STRM control.
    
    Commands:
    - /start - Start the bot
    - /help - Show help
    - /scan - Trigger scan
    - /status - Show status
    - /folders - List folders
    - /select - Select folders to scan
    - /history - Show scan history
    - /settings - Show settings
    """
    
    def __init__(self, token: Optional[str] = None):
        """Initialize Telegram bot"""
        config = get_config()
        self.token = token or config.telegram.token
        self.allowed_users = config.telegram.allowed_users
        self.notify_config = config.telegram.notify
        self.default_chat_id = int(config.telegram.chat_id) if str(config.telegram.chat_id).strip() else None
        self.topic_id = int(config.telegram.topic_id) if str(config.telegram.topic_id).strip() else None
        
        self._app: Optional[Application] = None
        self._running = False
        self._chat_ids: set = set()  # Store chat IDs for notifications
    
    def _check_auth(self, user_id: int) -> bool:
        """Check if user is authorized"""
        if not self.allowed_users:
            return True  # No restrictions
        return user_id in self.allowed_users

    def _extract_topic_id(self, update: Update) -> Optional[int]:
        """兼容不同场景提取 topic id。"""
        if not update:
            return None
        msg = update.effective_message
        if not msg:
            return None
        for attr in ("message_thread_id", "reply_to_top_message_id"):
            v = getattr(msg, attr, None)
            if v is not None:
                try:
                    return int(v)
                except Exception:
                    pass
        # 某些客户端中从 reply_to_message 推断 topic starter
        try:
            r = getattr(msg, "reply_to_message", None)
            if r is not None and getattr(r, "forum_topic_created", None):
                return int(getattr(r, "message_id", 0) or 0)
        except Exception:
            pass
        return None

    def _check_context(self, update: Update) -> bool:
        """Check if message comes from configured chat/topic."""
        if not update or not update.effective_chat:
            return False
        if self.default_chat_id and update.effective_chat.id != self.default_chat_id:
            return False
        # topic 限制临时放宽：同群管理员可在任意话题使用
        return True

    async def _reply(self, update: Update, text: str, parse_mode: Optional[str] = None, **kwargs) -> None:
        msg = update.effective_message
        if not msg:
            return
        if self.topic_id is not None:
            kwargs.setdefault("message_thread_id", self.topic_id)
        await msg.reply_text(text, parse_mode=parse_mode, **kwargs)
    
    async def _unauthorized(self, update: Update) -> None:
        """Send unauthorized message"""
        await update.message.reply_text(
            "❌ 未授权访问\n"
            "您的用户ID未在允许列表中。"
        )
    
    # ==================== Command Handlers ====================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        # Store chat ID for notifications
        self._chat_ids.add(update.effective_chat.id)
        
        await update.message.reply_text(
            "🎬 *OpenList2STRM Bot*\n\n"
            "欢迎使用 OpenList 到 STRM 转换工具！\n\n"
            "*可用命令:*\n"
            "/scan - 立即扫描更新\n"
            "/status - 查看当前状态\n"
            "/folders - 查看监控文件夹\n"
            "/select - 选择文件夹扫描\n"
            "/history - 查看扫描历史\n"
            "/settings - 查看设置\n"
            "/help - 显示帮助信息\n\n"
            f"您的用户ID: `{update.effective_user.id}`",
            parse_mode="Markdown",
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        await update.message.reply_text(
            "📖 *帮助信息*\n\n"
            "*扫描命令:*\n"
            "/scan - 扫描所有配置的文件夹\n"
            "/scan /path - 扫描指定文件夹\n"
            "/scan force - 强制全量扫描\n\n"
            "*状态命令:*\n"
            "/status - 查看扫描器和定时任务状态\n"
            "/history - 查看最近10次扫描记录\n\n"
            "*文件夹命令:*\n"
            "/folders - 列出所有监控的文件夹\n"
            "/select - 交互式选择文件夹扫描\n\n"
            "*设置命令:*\n"
            "/settings - 查看当前配置\n\n"
            "*其他:*\n"
            "/cancel - 取消正在进行的扫描",
            parse_mode="Markdown",
        )
    
    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /scan command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        from app.core.scanner import get_scanner
        from app.scheduler import get_scheduler_manager
        
        scanner = get_scanner()
        
        if scanner.is_running:
            await update.message.reply_text(
                "⚠️ 扫描正在进行中...\n"
                f"当前路径: `{scanner.progress.current_path}`\n"
                f"已扫描: {scanner.progress.files_scanned} 个文件",
                parse_mode="Markdown",
            )
            return
        
        # Parse arguments
        args = context.args or []
        force = "force" in args
        folders = [arg for arg in args if arg.startswith("/")]
        
        # Send starting message
        msg = await update.message.reply_text("🔄 开始扫描...")
        
        try:
            scheduler = get_scheduler_manager()
            result = await scheduler.trigger_now(
                folders=folders if folders else None,
                force=force,
            )
            
            # Format result
            text = (
                "✅ *扫描完成*\n\n"
                f"📁 扫描文件夹: {result['folders_scanned']}\n"
                f"📄 扫描文件: {result['total_files_scanned']}\n"
                f"✨ 新建 STRM: {result['total_files_created']}\n"
                f"🔄 更新 STRM: {result['total_files_updated']}\n"
                f"🗑️ 删除 STRM: {result['total_files_deleted']}"
            )
            
            await msg.edit_text(text, parse_mode="Markdown")
            
        except Exception as e:
            await msg.edit_text(f"❌ 扫描失败: {str(e)}")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        from app.core.scanner import get_scanner
        from app.core.cache import get_cache_manager
        from app.scheduler import get_scheduler_manager
        
        scanner = get_scanner()
        cache = get_cache_manager()
        scheduler = get_scheduler_manager()
        
        # Get stats
        stats = await cache.get_stats()
        last_scan = await cache.get_last_scan()
        
        # Build status text
        scanner_status = "🔄 扫描中" if scanner.is_running else "✅ 空闲"
        scheduler_status = "✅ 运行中" if scheduler._running else "⏸️ 已暂停"
        
        text = (
            "📊 *系统状态*\n\n"
            f"*扫描器:* {scanner_status}\n"
        )
        
        if scanner.is_running:
            p = scanner.progress
            text += (
                f"  当前: `{p.current_path}`\n"
                f"  已扫描: {p.files_scanned} 个文件\n"
            )
        
        text += (
            f"\n*定时任务:* {scheduler_status}\n"
            f"  Cron: `{get_config().schedule.cron}`\n"
        )
        
        # 兼容新版调度器：从任务 next_run 字段推导最近执行时间
        try:
            tasks = await scheduler.get_tasks()
            next_runs = [t.next_run for t in tasks if getattr(t, "next_run", None)]
            if next_runs:
                nearest = sorted(next_runs)[0]
                text += f"  下次执行: {nearest[:16].replace('T', ' ')}\n"
        except Exception:
            pass
        
        text += (
            f"\n*缓存统计:*\n"
            f"  总文件数: {stats['total_files']}\n"
            f"  STRM文件: {stats['total_strm']}\n"
            f"  总大小: {stats['total_size_human']}\n"
        )
        
        if last_scan:
            text += (
                f"\n*上次扫描:*\n"
                f"  时间: {last_scan.get('end_time', 'N/A')}\n"
                f"  状态: {last_scan.get('status', 'N/A')}\n"
            )
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_folders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /folders command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        from app.core.cache import get_cache_manager
        
        config = get_config()
        cache = get_cache_manager()
        
        text = "📁 *监控文件夹*\n\n"
        
        for folder in config.paths.source:
            files = await cache.get_all_files(folder)
            last = await cache.get_last_scan(folder)
            
            status_icon = "📂"
            last_time = last.get("end_time", "从未扫描") if last else "从未扫描"
            
            text += f"{status_icon} `{folder}`\n"
            text += f"   文件数: {len(files)} | 上次: {last_time}\n\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /select command - show folder selection keyboard"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        config = get_config()
        
        # Build inline keyboard
        keyboard = []
        for folder in config.paths.source:
            keyboard.append([
                InlineKeyboardButton(
                    f"📁 {folder}",
                    callback_data=f"scan:{folder}",
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 扫描全部", callback_data="scan:all"),
            InlineKeyboardButton("❌ 取消", callback_data="cancel"),
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📂 *选择要扫描的文件夹:*",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /history command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        from app.core.cache import get_cache_manager
        
        cache = get_cache_manager()
        history = await cache.get_scan_history(10)
        
        if not history:
            await update.message.reply_text("📜 暂无扫描历史")
            return
        
        text = "📜 *扫描历史*\n\n"
        
        for i, record in enumerate(history, 1):
            status_icon = "✅" if record.get("status") == "completed" else "❌"
            folder = record.get("folder", "N/A")
            time = record.get("end_time", record.get("start_time", "N/A"))
            created = record.get("files_created", 0)
            updated = record.get("files_updated", 0)
            
            text += f"{i}. {status_icon} `{folder}`\n"
            text += f"   {time} | +{created} 📝{updated}\n\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /settings command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        config = get_config()
        
        text = (
            "⚙️ *当前设置*\n\n"
            f"*OpenList:*\n"
            f"  地址: `{config.openlist.host}`\n"
            f"  超时: {config.openlist.timeout}s\n\n"
            f"*输出路径:* `{config.paths.output}`\n\n"
            f"*QoS限流:*\n"
            f"  QPS: {config.qos.qps}\n"
            f"  并发: {config.qos.max_concurrent}\n"
            f"  间隔: {config.qos.interval}ms\n\n"
            f"*定时任务:*\n"
            f"  启用: {'是' if config.schedule.enabled else '否'}\n"
            f"  Cron: `{config.schedule.cron}`\n\n"
            f"*增量更新:*\n"
            f"  启用: {'是' if config.incremental.enabled else '否'}\n"
            f"  检测方式: {config.incremental.check_method}"
        )
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command"""
        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await self._unauthorized(update)
            return
        
        from app.core.scanner import get_scanner
        
        scanner = get_scanner()
        
        if not scanner.is_running:
            await update.message.reply_text("ℹ️ 当前没有正在进行的扫描")
            return
        
        scanner.cancel()
        await update.message.reply_text("⏹️ 已请求取消扫描")
    
    # ==================== Callback Query Handler ====================
    
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()

        if not self._check_context(update):
            return
        if not self._check_auth(update.effective_user.id):
            await query.edit_message_text("❌ 未授权访问")
            return
        
        data = query.data
        
        if data.startswith("scan:"):
            folder = data[5:]
            
            if folder == "all":
                await query.edit_message_text("🔄 开始扫描所有文件夹...")
                folders = None
            else:
                await query.edit_message_text(f"🔄 开始扫描: `{folder}`", parse_mode="Markdown")
                folders = [folder]
            
            from app.scheduler import get_scheduler_manager
            
            try:
                scheduler = get_scheduler_manager()
                result = await scheduler.trigger_now(folders=folders)
                
                text = (
                    "✅ *扫描完成*\n\n"
                    f"📄 扫描文件: {result['total_files_scanned']}\n"
                    f"✨ 新建: {result['total_files_created']}\n"
                    f"🔄 更新: {result['total_files_updated']}\n"
                    f"🗑️ 删除: {result['total_files_deleted']}"
                )
                await query.edit_message_text(text, parse_mode="Markdown")
                
            except Exception as e:
                await query.edit_message_text(f"❌ 扫描失败: {str(e)}")
        
        elif data == "cancel":
            await query.edit_message_text("❌ 已取消")
    
    # ==================== Notification Methods ====================
    
    async def notify(self, message: str) -> None:
        """Send notification to configured chats/topics"""
        if not self._app:
            return

        targets = set(self._chat_ids)
        if self.default_chat_id:
            targets.add(self.default_chat_id)
        if not targets:
            return

        for chat_id in targets:
            try:
                kwargs = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                }
                if self.topic_id is not None:
                    kwargs["message_thread_id"] = self.topic_id
                await self._app.bot.send_message(**kwargs)
            except Exception as e:
                logger.warning(f"Failed to send notification to {chat_id}: {e}")
    
    async def notify_scan_start(self, folders: List[str]) -> None:
        """Notify scan start"""
        if not self.notify_config.on_scan_start:
            return
        
        folders_text = ", ".join(f"`{f}`" for f in folders)
        await self.notify(f"🔄 开始扫描: {folders_text}")
    
    async def notify_scan_complete(self, result: dict) -> None:
        """Notify scan completion"""
        if not self.notify_config.on_scan_complete:
            return

        # Compatible with both old dict summary and new list[ScanProgress]
        total_created = 0
        total_updated = 0
        total_deleted = 0

        if isinstance(result, list):
            total_created = sum(getattr(r, "files_created", 0) for r in result)
            total_updated = sum(getattr(r, "files_updated", 0) for r in result)
            total_deleted = sum(getattr(r, "files_deleted", 0) for r in result)
        elif isinstance(result, dict):
            total_created = result.get("total_files_created", result.get("created", 0))
            total_updated = result.get("total_files_updated", result.get("updated", 0))
            total_deleted = result.get("total_files_deleted", result.get("deleted", 0))

        await self.notify(
            f"✅ *扫描完成*\n"
            f"新建: {total_created} | "
            f"更新: {total_updated} | "
            f"删除: {total_deleted}"
        )
    
    async def notify_error(self, error: str) -> None:
        """Notify error"""
        if not self.notify_config.on_error:
            return
        
        await self.notify(f"❌ *错误*\n{error}")
    
    # ==================== Lifecycle Methods ====================
    
    async def start(self) -> None:
        """Start the Telegram bot"""
        if not self.token:
            logger.warning("Telegram bot token not configured")
            return
        
        if self._running:
            return
        
        # Build application
        self._app = Application.builder().token(self.token).build()
        
        # Add handlers
        self._app.add_handler(CommandHandler("start", self.cmd_start))
        self._app.add_handler(CommandHandler("help", self.cmd_help))
        self._app.add_handler(CommandHandler("scan", self.cmd_scan))
        self._app.add_handler(CommandHandler("status", self.cmd_status))
        self._app.add_handler(CommandHandler("folders", self.cmd_folders))
        self._app.add_handler(CommandHandler("select", self.cmd_select))
        self._app.add_handler(CommandHandler("history", self.cmd_history))
        self._app.add_handler(CommandHandler("settings", self.cmd_settings))
        self._app.add_handler(CommandHandler("cancel", self.cmd_cancel))
        self._app.add_handler(CallbackQueryHandler(self.callback_handler))
        
        # Start bot
        await self._app.initialize()
        await self._app.bot.set_my_commands([
            BotCommand("start", "开始使用机器人"),
            BotCommand("help", "查看帮助"),
            BotCommand("scan", "立即扫描"),
            BotCommand("status", "查看状态"),
            BotCommand("folders", "查看监控目录"),
            BotCommand("select", "选择目录扫描"),
            BotCommand("history", "查看扫描历史"),
            BotCommand("settings", "查看当前配置"),
            BotCommand("cancel", "取消正在进行的扫描"),
        ])
        await self._app.start()
        await self._app.updater.start_polling()

        if self.default_chat_id:
            self._chat_ids.add(self.default_chat_id)

        self._running = True
        logger.info("Telegram bot started")
    
    async def stop(self) -> None:
        """Stop the Telegram bot"""
        if self._app and self._running:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._running = False
            logger.info("Telegram bot stopped")


# Global bot instance
_bot: Optional[TelegramBot] = None


def get_telegram_bot() -> TelegramBot:
    """Get the global Telegram bot instance"""
    global _bot
    if _bot is None:
        _bot = TelegramBot()
    return _bot


async def start_telegram_bot() -> None:
    """Start the Telegram bot if enabled"""
    config = get_config()
    if config.telegram.enabled:
        bot = get_telegram_bot()
        await bot.start()


async def stop_telegram_bot() -> None:
    """Stop the Telegram bot"""
    global _bot
    if _bot:
        await _bot.stop()
        _bot = None
