"""企业微信智能机器人模板卡片构建（101032）。"""

from __future__ import annotations

import re
import uuid
from typing import Any


from app.config import get_settings
from app.system_options import build_button_selection, parse_option_list


def new_task_id() -> str:
    """生成 task_id，仅含数字、字母和 _-@，最长 128 字节。"""
    return re.sub(r"[^0-9A-Za-z_\-@]", "", uuid.uuid4().hex)


def build_button_interaction_card(
    *,
    title: str,
    desc: str = "",
    sub_title: str = "",
    task_id: str | None = None,
    horizontal_items: list[dict[str, Any]] | None = None,
    buttons: list[dict[str, Any]] | None = None,
    button_selection: dict[str, Any] | None = None,
    source_desc: str = "wecom-proxy",
    card_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 button_interaction 模板卡片（101032）。"""
    card: dict[str, Any] = {
        "card_type": "button_interaction",
        "source": {
            "icon_url": "https://wework.qpic.cn/wwpic/252813_jOfDHtcISzuodLa_1629280209/0",
            "desc": source_desc,
            "desc_color": 0,
        },
        "main_title": {
            "title": title[:26],
            "desc": desc[:30] if desc else "",
        },
        "button_list": buttons or [
            {"text": "确认", "style": 1, "key": "confirm"},
            {"text": "取消", "style": 2, "key": "cancel"},
        ],
        "task_id": task_id or new_task_id(),
    }

    if sub_title:
        card["sub_title_text"] = sub_title[:112]

    if horizontal_items:
        card["horizontal_content_list"] = horizontal_items[:6]

    if button_selection:
        card["button_selection"] = button_selection

    if card_action:
        card["card_action"] = card_action

    return card


def build_user_action_card(
    user_text: str,
    userid: str,
    chattype: str,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    """根据用户消息生成业务操作卡片。"""
    normalized = user_text.strip() or "（空）"
    tid = task_id or new_task_id()

    return build_button_interaction_card(
        title="请选择下一步操作",
        desc="wecom-proxy 智能助手",
        sub_title=f"您的输入：{normalized[:80]}",
        task_id=tid,
        horizontal_items=[
            {"keyname": "用户", "value": userid[:26]},
            {"keyname": "会话", "value": "群聊" if chattype == "group" else "单聊"},
            {"keyname": "内容长度", "value": str(len(normalized))},
        ],
        button_selection={
            "question_key": "user_role",
            "title": "您的身份",
            "disable": False,
            "option_list": [
                {"id": "role_admin", "text": "管理员"},
                {"id": "role_user", "text": "普通用户"},
            ],
            "selected_id": "role_user",
        },
        buttons=[
            {"text": "提交处理", "style": 1, "key": "submit"},
            {"text": "重新输入", "style": 2, "key": "retry"},
            {"text": "查看帮助", "style": 4, "key": "help"},
        ],
    )


def build_welcome_card(*, task_id: str | None = None, bind_url: str = "") -> dict[str, Any]:
    """进入会话欢迎卡片。"""
    start_button: dict[str, Any] = {"text": "开始绑定客户", "style": 1, "key": "start"}
    if bind_url:
        start_button = {
            "text": "开始绑定客户",
            "style": 4,
            "type": 1,
            "url": bind_url,
        }

    return build_button_interaction_card(
        title="欢迎使用CRM客户绑定助手",
        desc="",
        sub_title="",
        task_id=task_id or new_task_id(),
        horizontal_items=[
            #{"keyname": "方式一", "value": "发送：绑定客户"},
            #{"keyname": "方式二", "value": "点击下面按钮绑定客户"},
        ],
        buttons=[start_button],
        source_desc="CRM客户绑定助手",
    )


def build_button_clicked_card(
    *,
    event_key: str,
    task_id: str,
    selected_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """用户点击按钮后更新卡片内容。"""
    selection_desc = _format_selected_items(selected_items)
    action_label = _event_key_label(event_key)

    horizontal: list[dict[str, Any]] = [
        {"keyname": "操作", "value": action_label},
        {"keyname": "状态", "value": "已处理"},
    ]
    if selection_desc:
        horizontal.append({"keyname": "选择项", "value": selection_desc[:26]})

    return build_button_interaction_card(
        title="操作已收到",
        desc="感谢您的反馈",
        sub_title=f"您点击了：{action_label}",
        task_id=task_id,
        horizontal_items=horizontal,
        buttons=[
            {"text": "已完成", "style": 1, "key": "done"},
        ],
    )


def build_register_confirm_card(
    *,
    demand_content: str,
    userid: str,
    task_id: str | None = None,
    image_count: int = 0,
    upload_url: str = "",
    max_images: int = 3,
    system_option_id: str = "",
) -> dict[str, Any]:
    """需求登记确认卡片（上传直链 H5 + 卡片确认提交）。"""
    preview = demand_content[:80] + ("…" if len(demand_content) > 80 else "")
    image_desc = (
        f"已上传 {image_count}/{max_images} 张"
        if image_count
        else f"可选，最多 {max_images} 张"
    )
    system_options = parse_option_list(get_settings().registration_system_options)
    selected_system_id = system_option_id or (
        system_options[0]["id"] if system_options else ""
    )
    system_label = next(
        (item["text"] for item in system_options if item["id"] == selected_system_id),
        "",
    )

    horizontal: list[dict[str, Any]] = [
        {"keyname": "提交人", "value": userid[:26]},
        {"keyname": "内容长度", "value": str(len(demand_content))},
        {"keyname": "图片", "value": image_desc[:26]},
    ]
    if system_label:
        horizontal.insert(1, {"keyname": "所属系统", "value": system_label[:26]})
    _append_issue_list_link(horizontal)

    upload_button: dict[str, Any] = {"text": "上传图片", "style": 4, "key": "register_upload"}
    if upload_url:
        upload_button = {
            "text": "上传图片",
            "style": 4,
            "type": 1,
            "url": upload_url,
        }

    button_selection = None
    if system_options:
        button_selection = build_button_selection(
            options=system_options,
            selected_id=selected_system_id,
        )

    return build_button_interaction_card(
        title="需求登记确认",
        desc="选择系统后提交登记"[:30],
        sub_title=f"需求内容：{preview}",
        task_id=task_id or new_task_id(),
        horizontal_items=horizontal,
        button_selection=button_selection,
        buttons=[
            upload_button,
            {"text": "提交登记", "style": 1, "key": "register_submit"},
            {"text": "取消", "style": 2, "key": "register_cancel"},
        ],
        source_desc="需求登记",
    )


def build_register_success_card(
    *,
    task_id: str,
    demand_content: str,
    image_count: int = 0,
    system_name: str = "",
) -> dict[str, Any]:
    preview = demand_content[:80] + ("…" if len(demand_content) > 80 else "")
    horizontal: list[dict[str, Any]] = [
        {"keyname": "状态", "value": "已登记"},
        {"keyname": "字段", "value": "f9VtuW"},
    ]
    if system_name:
        horizontal.append({"keyname": "所属系统", "value": system_name[:26]})
    if image_count:
        horizontal.append({"keyname": "图片", "value": f"{image_count} 张"})
    _append_issue_list_link(horizontal)

    issue_list_url = get_settings().issue_list_url.strip()
    success_button: dict[str, Any] = {"text": "已完成", "style": 1, "key": "register_done"}
    if issue_list_url:
        success_button = {
            "text": "产品经理跟进",
            "style": 4,
            "type": 1,
            "url": issue_list_url,
        }

    return build_button_interaction_card(
        title="登记成功",
        desc="已写入智能表格",
        sub_title=f"需求内容：{preview}",
        task_id=task_id,
        horizontal_items=horizontal,
        buttons=[success_button],
        source_desc="需求登记",
    )


def build_register_failed_card(*, task_id: str, error: str) -> dict[str, Any]:
    return build_button_interaction_card(
        title="登记失败",
        desc="写入智能表格时出错",
        sub_title=error[:112],
        task_id=task_id,
        horizontal_items=[
            {"keyname": "状态", "value": "失败"},
        ],
        buttons=[
            {"text": "请重试", "style": 2, "key": "register_retry_hint"},
        ],
        source_desc="需求登记",
    )


def build_register_cancelled_card(*, task_id: str) -> dict[str, Any]:
    return build_button_interaction_card(
        title="已取消登记",
        desc="未写入智能表格",
        task_id=task_id,
        horizontal_items=[
            {"keyname": "状态", "value": "已取消"},
        ],
        buttons=[
            {"text": "关闭", "style": 2, "key": "register_done"},
        ],
        source_desc="需求登记",
    )


def wrap_template_card(card: dict[str, Any]) -> dict[str, Any]:
    """包装为被动回复 template_card 消息（101031）。"""
    return {"msgtype": "template_card", "template_card": card}


def wrap_update_template_card(
    card: dict[str, Any],
    userids: list[str] | None = None,
) -> dict[str, Any]:
    """包装为模板卡片更新回复（101031）。"""
    reply: dict[str, Any] = {
        "response_type": "update_template_card",
        "template_card": card,
    }
    if userids:
        reply["userids"] = userids
    return reply


def _append_issue_list_link(horizontal: list[dict[str, Any]]) -> None:
    """在横向内容中追加问题清单链接（若已配置 ISSUE_LIST_URL）。"""
    issue_list_url = get_settings().issue_list_url.strip()
    if issue_list_url:
        horizontal.append(
            {
                "keyname": "问题清单",
                "value": "打开问题清单"[:26],
                "type": 1,
                "url": issue_list_url,
            }
        )


def _event_key_label(event_key: str) -> str:
    labels = {
        "confirm": "确认",
        "cancel": "取消",
        "submit": "提交处理",
        "retry": "重新输入",
        "help": "查看帮助",
        "start": "开始咨询",
        "intro": "功能介绍",
        "done": "已完成",
    }
    return labels.get(event_key, event_key or "未知")


def _format_selected_items(selected_items: list[dict[str, Any]] | None) -> str:
    if not selected_items:
        return ""

    parts: list[str] = []
    for item in selected_items:
        question = item.get("question_key", "")
        option_ids = (item.get("option_ids") or {}).get("option_id") or []
        if option_ids:
            parts.append(f"{question}={','.join(option_ids)}")
    return "; ".join(parts)
