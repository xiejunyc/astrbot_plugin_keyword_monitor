from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.core.platform import MessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain
from astrbot.api import AstrBotConfig
from astrbot.api.event.filter import PermissionType
import asyncio
import re
import json
import os

@register("keyword_monitor", "NMpancake", "这是一个关键词监控插件", "1.0.0")
class KeywordMonitorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.context = context
        self.keywords = self.config.get('keywords', [])
        self.white_list = self.config.get('white_list', [])
        self.send_qq = self.config.get('send_qq')
        self.enable_sendgroup = self.config.get("enable_sendgroup", False)
        self.send_group = self.config.get('send_group')

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def monitor_keywords(self, event: AstrMessageEvent):
        """监控群聊中的关键词"""
        try:
            # 检查是否在白名单群聊中
            group_id = event.get_group_id()
            if group_id not in self.white_list:
                return
            
            # 检查消息内容是否包含关键词
            message = event.message_str
            for keyword in self.keywords:
                if keyword in message:
                    # 获取发送者信息
                    sender_id = event.get_sender_id()
                    sender_name = event.get_sender_name()
                    
                    # 构建通知消息
                    alert_msg = (
                        f"⚠️ 监控词警报 ⚠️\n"
                        f"监控词: {keyword}\n"
                        f"群号: {group_id}\n"
                        f"发送者: {sender_name}({sender_id})\n"
                        f"消息内容: {message[:50]}{'...' if len(message) > 50 else ''}"
                    )
                    
                    # 发送私聊通知给管理员
                    await self.send_private_alert(event, alert_msg)
                    logger.warning(f"检测到关键词: {keyword} 在群 {group_id} 由 {sender_id} 发送")
                    break
        except Exception as e:
            logger.error(f"监控插件出错: {str(e)}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("添加监控词")
    async def add_keyword(self, event: AstrMessageEvent, keyword: str = ""):        
        if not keyword:
            yield event.plain_result("❌ 用法：添加监控词 [关键词]")
            return
        
        if keyword in self.keywords:
            yield event.plain_result(f"❌ 关键词 '{keyword}' 已存在")
        else:
            self.keywords.append(keyword)
            self.config.save_config()
            yield event.plain_result(f"✅ 已添加监控词：{keyword}")
            logger.info(f"管理员添加关键词: {keyword}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("删除监控词")
    async def del_keyword(self, event: AstrMessageEvent, keyword: str = ""):
        if not keyword:
            yield event.plain_result("❌ 用法：删除监控词 [关键词]")
            return
        
        if keyword not in self.keywords:
            yield event.plain_result(f"❌ 关键词 '{keyword}' 不存在")
        else:
            self.keywords.remove(keyword)
            self.config.save_config()
            yield event.plain_result(f"✅ 已删除监控词：{keyword}")
            logger.info(f"管理员删除关键词: {keyword}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("监控词列表")
    async def list_keywords(self, event: AstrMessageEvent):      
        if not self.keywords:
            yield event.plain_result("🔍 当前没有监控关键词")
        else:
            keywords_list = "\n".join([f"• {kw}" for kw in self.keywords])
            yield event.plain_result(f"📝 监控词列表：\n{keywords_list}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("添加监控群")
    async def add_monitor_group(self, event: AstrMessageEvent, group_id: str = ""):    
        if not group_id:
            yield event.plain_result("❌ 用法：添加监控群 [纯数字群号]")
            return
            
        if not group_id.isdigit():
            yield event.plain_result("❌ 用法：添加监控群 [纯数字群号]")
            return
        
        if group_id in self.white_list:
            yield event.plain_result(f"❌ 群 {group_id} 已在监控列表中")
        else:
            self.white_list.append(group_id)
            self.config.save_config()
            yield event.plain_result(f"✅ 已添加监控群：{group_id}")
            logger.info(f"管理员添加监控群: {group_id}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("删除监控群")
    async def del_monitor_group(self, event: AstrMessageEvent, group_id: str = ""):     
        if not group_id:
            yield event.plain_result("❌ 用法：删除监控群 [纯数字群号]")
            return

        if not group_id.isdigit():
            yield event.plain_result("❌ 用法：删除监控群 [纯数字群号]")
            return
        
        if group_id not in self.white_list:
            yield event.plain_result(f"❌ 群 {group_id} 不在监控列表中")
        else:
            self.white_list.remove(group_id)
            self.config.save_config()
            yield event.plain_result(f"✅ 已移除监控群：{group_id}")
            logger.info(f"管理员移除监控群: {group_id}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("监控群列表")
    async def list_monitor_groups(self, event: AstrMessageEvent):     
        if not self.white_list:
            yield event.plain_result("🔍 当前没有监控群")
        else:
            groups_list = "\n".join([f"• {g}" for g in self.white_list])
            yield event.plain_result(f"📝 监控群列表：\n{groups_list}")
    
    async def send_private_alert(self, event: AstrMessageEvent, message: str):
        """发送私聊通知给管理员 - 使用context主动发送消息"""
        if self.enable_sendgroup:
            if not self.send_group or not self.send_group.isdigit():
                logger.error("QQ群无效（为空或非数字）")
                return

            try:
                await event.bot.send_group_msg(group_id=self.send_group, message=message)
                logger.info(f"已向群聊 {self.send_group} 发送警报")
            except Exception as e:
                logger.error(f"发送警报失败：{e}")
        else:
            if not self.send_qq or not self.send_qq.isdigit():
                logger.error("QQ号无效（为空或非数字）")
                return

            try:
                await event.bot.send_private_msg(user_id=self.send_qq, message=message)
                logger.info(f"已向好友 {self.send_qq} 发送警报")
            except Exception as e:
                logger.error(f"发送警报失败：{e}")
           

    async def terminate(self):
        """插件卸载时执行"""
        logger.info("监控插件已卸载")
