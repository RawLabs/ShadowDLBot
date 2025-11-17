"""
Telegram-facing handlers for ShadowSafe.
"""
from __future__ import annotations

import asyncio
import html
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from telegram import InputFile, Message, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..scanner.core import Issue, ScanResult, scan_file

LOGGER = logging.getLogger(__name__)


def register(
    application: Application, settings: Mapping[str, object] | None = None
) -> None:
    """Attach command/message handlers to the Telegram application."""
    handler_state = _HandlerState(HandlerConfig.from_settings(settings or {}))

    application.add_handler(CommandHandler("start", handler_state.cmd_start))
    application.add_handler(CommandHandler("help", handler_state.cmd_help))
    application.add_handler(CommandHandler("about", handler_state.cmd_about))
    application.add_handler(CommandHandler("privacy", handler_state.cmd_privacy))
    application.add_handler(CommandHandler("inspect", handler_state.cmd_inspect))

    file_filters = (
        filters.ChatType.PRIVATE
        & (
            filters.Document.ALL
            | filters.PHOTO
            | filters.VIDEO
            | filters.ANIMATION
        )
    )
    application.add_handler(
        MessageHandler(file_filters, handler_state.handle_private_file)
    )


def format_report(scan_result: ScanResult) -> str:
    """Convert a ScanResult into an HTML report."""
    verdict = _verdict_emoji(scan_result.issues)
    lines = [f"<b>{verdict} ShadowSafe Report</b>"]
    lines.append(
        f"<b>File:</b> {html.escape(scan_result.file_name)} ({_format_size(scan_result.size_bytes)})"
    )
    lines.append(f"<b>Type:</b> {html.escape(scan_result.detected_type)}")
    if scan_result.extension_mismatch:
        lines.append(f"<b>Extension mismatch:</b> {html.escape(scan_result.extension_mismatch)}")
    if scan_result.hashes:
        sha = scan_result.hashes.get("sha256", "")
        md5 = scan_result.hashes.get("md5", "")
        if sha:
            lines.append(f"<b>SHA256:</b> <code>{html.escape(sha)}</code>")
        if md5:
            lines.append(f"<b>MD5:</b> <code>{html.escape(md5)}</code>")
    if scan_result.blocklist_hits:
        hits = ", ".join(scan_result.blocklist_hits)
        lines.append(f"<b>Blocklist hits:</b> {html.escape(hits)}")
    else:
        lines.append("<b>Blocklist:</b> no matches")

    lines.append("<b>Privacy:</b>")
    lines.extend(
        [
            f"• EXIF: {html.escape(scan_result.metadata_summary.get('exif_present', 'unknown'))}",
            f"• GPS: {html.escape(scan_result.metadata_summary.get('gps_present', 'unknown'))}",
            f"• Camera: {html.escape(scan_result.metadata_summary.get('camera_model', 'unknown'))}",
        ]
    )

    structured = _format_structural_details(scan_result)
    if structured:
        lines.append("<b>Structure:</b>")
        lines.extend(structured)

    if scan_result.issues:
        issue_lines = []
        for issue in scan_result.issues:
            line = (
                f"• {issue.severity.upper()} - {html.escape(issue.category)}: "
                f"{html.escape(issue.message)}"
            )
            if issue.explanation:
                line += f" ({html.escape(issue.explanation)})"
            issue_lines.append(line)
        lines.append("<b>Indicators:</b>")
        lines.extend(issue_lines)
    else:
        lines.append("• No suspicious indicators detected.")

    overall = _overall_verdict(scan_result.issues, scan_result.risk_score)
    lines.append(f"<b>Risk score:</b> {scan_result.risk_score}/100")
    lines.append(f"<i>Overall: {overall}</i>")
    lines.append(
        "<i>ShadowSafe checks for structural red flags but cannot guarantee absolute safety.</i>"
    )
    return "\n".join(lines)


def _format_structural_details(result: ScanResult) -> list[str]:
    details: list[str] = []
    for key, info in result.per_scanner_details.items():
        if key == "pdf":
            details.append(
                f"• PDF: JS={'yes' if info.get('has_javascript') else 'no'}, embedded_files={info.get('embedded_files', 0)}, actions={info.get('auto_actions', 0)}"
            )
        elif key == "image":
            notes = ", ".join(info.get("notes", [])) or "clean"
            details.append(
                f"• Image: format={info.get('detected_format', 'unknown')}, appended_data={'yes' if info.get('has_appended_data') else 'no'}, notes={notes}"
            )
        elif key == "video":
            details.append(
                f"• Video: container_ok={'yes' if info.get('container_ok', True) else 'no'}, appended_data={'yes' if info.get('has_appended_data') else 'no'}"
            )
        elif key == "archive":
            details.append(
                f"• Archive: executables={'yes' if info.get('has_executables') else 'no'}, macros={'yes' if info.get('has_macros') else 'no'}, compression_ratio={info.get('compression_ratio', 0)}"
            )
        elif key == "heuristics":
            details.append(
                "• Heuristics: mean_entropy="
                f"{info.get('mean_entropy')} high_entropy_ratio={info.get('high_entropy_ratio')}"
            )
        elif key == "yara":
            matches = ", ".join(info.get("matches", []))
            details.append(f"• YARA: {matches or 'no matches'}")
    return details


def _verdict_emoji(issues: list[Issue]) -> str:
    severities = {issue.severity for issue in issues}
    if "red" in severities:
        return "🔴"
    if "yellow" in severities:
        return "🟡"
    return "🟢"


def _overall_verdict(issues: list[Issue], risk_score: int) -> str:
    if risk_score >= 70:
        return "High risk indicators. Exercise caution."
    if risk_score >= 30:
        return "Some warnings detected. Review before sharing."
    if issues:
        return "Low risk indicators with minor warnings."
    return "Low risk indicators. Nothing suspicious found."


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}B"
        size /= 1024
    return f"{size:.1f}TB"


@dataclass
class HandlerConfig:
    temp_directory: Path
    enable_sanitized_copy: bool
    max_file_size_mb: int

    @classmethod
    def from_settings(cls, settings: Mapping[str, object]) -> "HandlerConfig":
        temp_dir = Path(
            settings.get("temp_directory") or tempfile.gettempdir()
        )
        temp_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            temp_directory=temp_dir,
            enable_sanitized_copy=bool(settings.get("enable_sanitized_copy", False)),
            max_file_size_mb=int(settings.get("max_file_size_mb", 200)),
        )


@dataclass
class _FilePayload:
    file_id: str
    file_name: str
    mime_type: Optional[str]


class _HandlerState:
    def __init__(self, config: HandlerConfig):
        self.config = config

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(
            update,
            "Send me a file in DM and I will inspect it. "
            "In groups, reply with /inspect to a file message.",
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(
            update,
            "DM usage: send a file → get a report.\n"
            "Group usage: reply to a file with /inspect to trigger a scan.",
        )

    async def cmd_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(
            update,
            "ShadowSafe looks for structural red flags and metadata leaks. "
            "No guarantees, no file storage, privacy-first.",
        )

    async def cmd_privacy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(
            update,
            "Privacy:\n"
            "• Files are scanned locally and deleted right after processing.\n"
            "• Optional logs can record timestamp/size/verdict only.\n"
            "• No uploads to third-party scanners by default.",
        )

    async def handle_private_file(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.message:
            return
        payload = _extract_file_payload(update.message)
        if not payload:
            await update.message.reply_text("Send a document, photo, or video to inspect.")
            return
        await self._process_payload(update.message, payload, context)

    async def cmd_inspect(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if not message:
            return
        if message.chat.type == ChatType.PRIVATE:
            await message.reply_text("In DM just send me a file and I'll scan it automatically.")
            return
        if not message.reply_to_message:
            await message.reply_text("Reply to a message with a file and send /inspect to analyze it.")
            return
        payload = _extract_file_payload(message.reply_to_message)
        if not payload:
            await message.reply_text("The replied message does not contain a supported file.")
            return
        await self._process_payload(message.reply_to_message, payload, context)

    async def _process_payload(
        self,
        target_message: Message,
        payload: _FilePayload,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        temp_dir = Path(
            tempfile.mkdtemp(prefix="shadowsafe-", dir=self.config.temp_directory)
        )
        file_path = temp_dir / payload.file_name
        sanitized_bytes: Optional[bytes] = None
        sanitized_name: Optional[str] = None
        try:
            tg_file = await context.bot.get_file(payload.file_id)
            await tg_file.download_to_drive(custom_path=str(file_path))
            if file_path.stat().st_size > self.config.max_file_size_mb * 1024 * 1024:
                await target_message.reply_text("File exceeds the maximum allowed size for scanning.")
                return
            scan_result = await asyncio.to_thread(
                scan_file,
                file_path,
                payload.mime_type,
                enable_sanitization=self.config.enable_sanitized_copy,
            )
            if (
                self.config.enable_sanitized_copy
                and scan_result.sanitized_file_path
                and scan_result.sanitized_file_path.exists()
            ):
                sanitized_name = scan_result.sanitized_file_path.name
                sanitized_bytes = scan_result.sanitized_file_path.read_bytes()
            report = format_report(scan_result)
            await target_message.reply_text(
                report,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            if sanitized_bytes and sanitized_name:
                await target_message.reply_document(
                    document=InputFile(
                        sanitized_bytes, filename=sanitized_name
                    ),
                    caption="Here’s a sanitized copy with metadata stripped.",
                )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Failed to process file", exc_info=exc)
            await target_message.reply_text("An error occurred during scanning. Please try again later.")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _reply(self, update: Update, text: str) -> None:
        message = update.effective_message
        if message:
            await message.reply_text(text, disable_web_page_preview=True)


def _extract_file_payload(message: Message) -> Optional[_FilePayload]:
    if message.document:
        doc = message.document
        name = doc.file_name or f"document-{doc.file_unique_id}"
        return _FilePayload(doc.file_id, name, doc.mime_type)
    if message.photo:
        photo = message.photo[-1]
        name = f"photo-{photo.file_unique_id}.jpg"
        return _FilePayload(photo.file_id, name, "image/jpeg")
    if message.video:
        video = message.video
        name = video.file_name or f"video-{video.file_unique_id}.mp4"
        return _FilePayload(video.file_id, name, video.mime_type or "video/mp4")
    if message.animation:
        animation = message.animation
        name = animation.file_name or f"animation-{animation.file_unique_id}.mp4"
        return _FilePayload(animation.file_id, name, animation.mime_type or "video/mp4")
    return None
