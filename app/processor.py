from __future__ import annotations

import logging
import re
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from app.config import get_settings
from app.registrations import MAX_REGISTRATION_IMAGES, registration_store
from app.smartsheet import add_demand_record
from app.system_options import parse_option_list, parse_system_selection
from app.crm_bind_routes import build_crm_bind_page_url
from app.upload_routes import build_upload_page_url
from app.template_cards import (
    build_button_clicked_card,
    build_register_cancelled_card,
    build_register_confirm_card,
    build_register_failed_card,
    build_register_success_card,
    build_user_action_card,
    build_welcome_card,
    new_task_id,
    wrap_template_card,
    wrap_update_template_card,
)

logger = logging.getLogger(__name__)

REGISTER_SUBMIT_KEY = "register_submit"
REGISTER_CANCEL_KEY = "register_cancel"


@dataclass
class StreamSession:
    stream_id: str
    user_text: str
    step: int = 0
    finished: bool = False
    chunks: list[str] = field(default_factory=list)


class MessageProcessor:
    """将企业微信回调加工为被动回复消息。"""

    def __init__(self, max_seen: int = 2000) -> None:
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()
        self._streams: dict[str, StreamSession] = {}
        self._max_seen = max_seen

    def handle(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        msgid = payload.get("msgid")
        if msgid and self._is_duplicate(msgid):
            logger.info("重复回调已忽略 msgid=%s", msgid)
            return None

        msgtype = payload.get("msgtype")
        if msgtype == "event":
            return self._handle_event(payload)
        return self._handle_message(payload)

    def _handle_event(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        event = payload.get("event") or {}
        event_type = event.get("eventtype")

        if event_type == "enter_chat":
            return self._build_welcome_reply(payload)

        if event_type == "template_card_event":
            return self._handle_template_card_event(payload, event)

        if event_type == "feedback_event":
            feedback = event.get("feedback_event") or {}
            logger.info("用户反馈: %s", feedback)
            return None

        if event_type == "stream_refresh":
            return self._handle_stream_refresh(payload)

        logger.warning("未处理的事件类型: %s", event_type)
        return None

    def _handle_template_card_event(
        self,
        payload: dict[str, Any],
        event: dict[str, Any],
    ) -> dict[str, Any] | None:
        card_event = event.get("template_card_event") or {}
        card_type = card_event.get("card_type", "")
        if card_type != "button_interaction":
            logger.info("暂不支持更新的卡片类型: %s", card_type)
            return None

        event_key = card_event.get("event_key", "")
        task_id = card_event.get("task_id", "")
        selected_items = (card_event.get("selected_items") or {}).get("selected_item")

        logger.info(
            "模板卡片点击: event_key=%s task_id=%s selected=%s",
            event_key,
            task_id,
            selected_items,
        )

        registration = registration_store.get(task_id)
        if registration is not None:
            self._apply_registration_selection(registration, selected_items)
            updated = self._handle_registration_card_event(
                event_key=event_key,
                registration=registration,
                card_task_id=task_id,
            )
        else:
            updated = build_button_clicked_card(
                event_key=event_key,
                task_id=task_id,
                selected_items=selected_items,
            )

        from_info = payload.get("from") or {}
        userid = from_info.get("userid")
        userids = [userid] if userid and payload.get("chattype") == "group" else None
        return wrap_update_template_card(updated, userids=userids)

    def _build_welcome_reply(self, payload: dict[str, Any]) -> dict[str, Any]:
        from_info = payload.get("from") or {}
        userid = from_info.get("userid", "")
        bind_url = build_crm_bind_page_url(userid) if userid else ""
        if userid and not bind_url:
            logger.warning("未配置 PUBLIC_BASE_URL，欢迎卡片无法打开 CRM 绑定 H5")
        return wrap_template_card(build_welcome_card(bind_url=bind_url))

    def _apply_registration_selection(
        self,
        registration,
        selected_items: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> None:
        options = parse_option_list(get_settings().registration_system_options)
        selection = parse_system_selection(selected_items, options=options)
        if selection is None:
            return
        option_id, system_name = selection
        registration_store.update_system(
            registration.task_id,
            option_id=option_id,
            system_name=system_name,
        )
        registration.system_option_id = option_id
        registration.system_name = system_name

    def _build_registration_confirm_card(self, registration, *, task_id: str) -> dict[str, Any]:
        return build_register_confirm_card(
            demand_content=registration.demand_content,
            userid=registration.userid,
            task_id=task_id,
            image_count=len(registration.uploaded_images),
            upload_url=build_upload_page_url(registration.task_id, registration.userid),
            system_option_id=registration.system_option_id,
        )

    def _handle_registration_card_event(
        self,
        *,
        event_key: str,
        registration,
        card_task_id: str,
    ) -> dict[str, Any]:
        primary_task_id = registration.task_id
        content = registration.demand_content
        image_count = len(registration.uploaded_images)

        if event_key == REGISTER_CANCEL_KEY:
            registration_store.clear(primary_task_id, registration.userid)
            return build_register_cancelled_card(task_id=card_task_id)

        if event_key != REGISTER_SUBMIT_KEY:
            return self._build_registration_confirm_card(
                registration,
                task_id=card_task_id,
            )

        images = registration_store.list_smartsheet_images(primary_task_id)
        ok, errmsg = add_demand_record(
            content,
            userid=registration.userid,
            system=registration.system_name or None,
            images=images or None,
        )
        registration_store.clear(primary_task_id, registration.userid)

        if ok:
            return build_register_success_card(
                task_id=card_task_id,
                demand_content=content,
                image_count=image_count,
                system_name=registration.system_name,
            )
        return build_register_failed_card(task_id=card_task_id, error=errmsg)

    def _handle_message(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        msgtype = payload.get("msgtype")

        if msgtype == "stream":
            return self._handle_stream_refresh(payload)

        from_info = payload.get("from") or {}
        userid = from_info.get("userid", "unknown")
        chattype = payload.get("chattype", "single")

        if msgtype == "image":
            return self._reply_registration_upload_hint()

        user_text = self._extract_user_text(payload)
        if user_text is None:
            if self._extract_image_urls(payload):
                return self._reply_registration_upload_hint()
            logger.info("暂不支持的消息类型: %s", msgtype)
            return wrap_template_card(
                build_user_action_card(
                    user_text=f"收到 {msgtype} 类型消息",
                    userid=userid,
                    chattype=chattype,
                )
            )

        normalized = user_text.strip()

        if normalized in {"绑定客户", "开始绑定客户"}:
            return self._build_welcome_reply(payload)

        is_register, demand_content = self._parse_registration_text(normalized)
        if is_register:
            return self._handle_registration_message(
                demand_content,
                userid,
                payload=payload,
            )

        if normalized.startswith("/help"):
            return self._reply_help_stream()

        if normalized.startswith("/echo "):
            return self._reply_stream(normalized[6:].strip() or "(空)")

        if normalized in {"ping", "测试", "test"}:
            return self._reply_stream(
                f"pong · 用户 `{userid}` · 会话 `{chattype}` · 服务正常"
            )

        if self._should_reply_stream(normalized):
            return self._reply_stream_from_text(normalized, payload)

        return wrap_template_card(
            build_user_action_card(normalized, userid, chattype)
        )

    def _handle_registration_message(
        self,
        demand_content: str,
        userid: str,
        *,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not demand_content:
            return self._reply_stream(
                "请在「登记」后附上需求内容，例如：\n\n"
                "登记 希望优化报表导出速度\n\n"
                "发送确认卡片后，请选择所属系统，点「上传图片」附加截图（最多 3 张），"
                "完成后返回卡片点击「提交登记」。"
            )

        task_id = new_task_id()
        registration_store.create(
            task_id=task_id,
            demand_content=demand_content,
            userid=userid,
            chattype=str(payload.get("chattype") or "single"),
        )
        upload_url = build_upload_page_url(task_id, userid)
        logger.info("创建登记会话 task_id=%s userid=%s", task_id, userid)

        if not upload_url:
            return self._reply_stream(
                "登记会话已创建，但未配置 PUBLIC_BASE_URL，无法打开 H5 上传页。\n"
                "请在 .env 中设置 PUBLIC_BASE_URL 后重试。"
            )

        return wrap_template_card(
            build_register_confirm_card(
                demand_content=demand_content,
                userid=userid,
                task_id=task_id,
                upload_url=upload_url,
            )
        )

    def _reply_registration_upload_hint(self) -> dict[str, Any]:
        return self._reply_stream(
            "请点击登记确认卡片中的「上传图片」附加截图（最多 "
            f"{MAX_REGISTRATION_IMAGES} 张），完成后返回卡片点击「提交登记」。"
        )

    @staticmethod
    def _parse_registration_text(text: str) -> tuple[bool, str]:
        """解析包含「登记」的消息，返回 (是否登记意图, 需求内容)。"""
        idx = text.find("登记")
        if idx == -1:
            return False, ""

        content = text[idx + len("登记") :].strip()
        content = re.sub(r"^[：:\-,，\s]+", "", content)
        return True, content

    def _should_reply_stream(self, text: str) -> bool:
        return text.startswith("/stream")

    def _reply_help_stream(self) -> dict[str, Any]:
        return self._reply_stream(
            "可用指令：\n"
            "- `登记 需求内容` 提交需求到智能表格\n"
            "- 登记后选择所属系统，点卡片「上传图片」，完成后返回点「提交登记」\n"
            "- `/help` 查看帮助\n"
            "- `/echo 文本` 流式回显\n"
            "- `/stream 文本` 流式回复\n"
            "- 发送任意文本 → 按钮交互模板卡片\n"
            "- 进入会话 → 欢迎模板卡片"
        )

    def _reply_stream(self, content: str) -> dict[str, Any]:
        stream_id = self._new_stream_id()
        self._streams[stream_id] = StreamSession(
            stream_id=stream_id,
            user_text=content,
            chunks=[content],
        )
        return {
            "msgtype": "stream",
            "stream": {"id": stream_id, "finish": True, "content": content},
        }

    def _reply_stream_from_text(
        self,
        user_text: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        from_info = payload.get("from") or {}
        userid = from_info.get("userid", "unknown")
        chattype = payload.get("chattype", "single")
        content = user_text.removeprefix("/stream").strip()
        reply = self.process_text(content, userid=userid, chattype=chattype)

        stream_id = self._new_stream_id()
        session = StreamSession(
            stream_id=stream_id,
            user_text=content,
            chunks=self._build_stream_chunks(reply),
        )
        self._streams[stream_id] = session

        return {
            "msgtype": "stream",
            "stream": {
                "id": stream_id,
                "finish": len(session.chunks) <= 1,
                "content": session.chunks[0],
            },
        }

    def _handle_stream_refresh(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        stream_info = payload.get("stream") or {}
        stream_id = stream_info.get("id") or stream_info.get("stream_id")
        if not stream_id:
            logger.warning("流式刷新缺少 stream.id")
            return None

        session = self._streams.get(stream_id)
        if not session:
            return {
                "msgtype": "stream",
                "stream": {
                    "id": stream_id,
                    "finish": True,
                    "content": "会话已过期，请重新发送消息。",
                },
            }

        session.step += 1
        if session.step >= len(session.chunks):
            session.finished = True
            return {
                "msgtype": "stream",
                "stream": {
                    "id": stream_id,
                    "finish": True,
                    "content": session.chunks[-1],
                },
            }

        return {
            "msgtype": "stream",
            "stream": {
                "id": stream_id,
                "finish": False,
                "content": session.chunks[session.step],
            },
        }

    def _extract_user_text(self, payload: dict[str, Any]) -> str | None:
        msgtype = payload.get("msgtype")
        if msgtype == "text":
            text = payload.get("text") or {}
            content = text.get("content", "")
            return self._strip_bot_mention(content)

        if msgtype == "voice":
            voice = payload.get("voice") or {}
            return voice.get("content") or voice.get("recognition")

        if msgtype == "mixed":
            items = (payload.get("mixed") or {}).get("msg_item") or []
            parts: list[str] = []
            for item in items:
                if item.get("msgtype") == "text":
                    parts.append((item.get("text") or {}).get("content", ""))
            merged = "\n".join(part for part in parts if part)
            return self._strip_bot_mention(merged) if merged else None

        return None

    @staticmethod
    def _extract_image_urls(payload: dict[str, Any]) -> list[str]:
        msgtype = payload.get("msgtype")
        urls: list[str] = []

        if msgtype == "image":
            url = (payload.get("image") or {}).get("url")
            if url:
                urls.append(url.strip())
            return urls

        if msgtype == "mixed":
            for item in (payload.get("mixed") or {}).get("msg_item") or []:
                if item.get("msgtype") != "image":
                    continue
                url = (item.get("image") or {}).get("url")
                if url:
                    urls.append(url.strip())
        return urls

    @staticmethod
    def _strip_bot_mention(content: str) -> str:
        return re.sub(r"^@\S+\s*", "", content.strip())

    @staticmethod
    def _build_stream_chunks(reply: str) -> list[str]:
        if len(reply) <= 80:
            return [reply]
        return ["正在处理你的消息…", reply]

    @staticmethod
    def process_text(user_text: str, userid: str, chattype: str) -> str:
        """核心业务加工逻辑，可按需替换为 LLM / 工单系统等。"""
        normalized = user_text.strip()
        logger.info("用户原始文本: %s", normalized)
        logger.info("用户ID: %s", userid)
        logger.info("会话类型: %s", chattype)

        if not normalized:
            return "请输入有效内容。"

        return (
            f"**加工结果**\n\n"
            f"- 原文：{normalized}\n"
            f"- 字符数：{len(normalized)}\n"
            f"- 大写：{normalized.upper()}\n"
            f"- 来自：`{userid}`（{chattype}）"
        )

    def _is_duplicate(self, msgid: str) -> bool:
        with self._lock:
            if msgid in self._seen:
                return True
            self._seen[msgid] = None
            while len(self._seen) > self._max_seen:
                self._seen.popitem(last=False)
            return False

    @staticmethod
    def _new_stream_id() -> str:
        return uuid.uuid4().hex
