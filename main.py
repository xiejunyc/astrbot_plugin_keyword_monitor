from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.core.platform import MessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain
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
        self.admin_qq = self.config.get('admin_qq')
        self.enable_sendgroup_list = self.config.get("enable_sendgroup_list", False)
        self.sendgroup_list = self.config.get('sendgroup_list', [])

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
                        f"⚠️ 检测到关键词警报 ⚠️\n"
                        f"关键词: {keyword}\n"
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

    @filter.command("添加监控词", permission_type=filter.PermissionType.ADMIN)
    async def add_keyword(self, event: AstrMessageEvent, keyword: str = None):
        sender_qq = event.get_sender_id()
        if str(sender_qq) != str(self.admin_qq):
            yield event.plain_result("❌ 权限不足！仅管理员可使用此命令")
            return
        
        if not keyword:
            yield event.plain_result("❌ 用法：添加监控词 [关键词]")
            return
        
        if keyword in self.keywords:
            yield event.plain_result(f"❌ 关键词 '{keyword}' 已存在")
        else:
            self.keywords.append(keyword)
            self.save_config()
            yield event.plain_result(f"✅ 已添加监控词：{keyword}")
            logger.info(f"管理员添加关键词: {keyword}")

    @filter.command("删除监控词", permission_type=filter.PermissionType.ADMIN)
    async def del_keyword(self, event: AstrMessageEvent, keyword: str = None):
        sender_qq = event.get_sender_id()
        if str(sender_qq) != str(self.admin_qq):
            yield event.plain_result("❌ 权限不足！仅管理员可使用此命令")
            return
        
        if not keyword:
            yield event.plain_result("❌ 用法：删除监控词 [关键词]")
            return
        
        if keyword not in self.keywords:
            yield event.plain_result(f"❌ 关键词 '{keyword}' 不存在")
        else:
            self.keywords.remove(keyword)
            self.save_config()
            yield event.plain_result(f"✅ 已删除监控词：{keyword}")
            logger.info(f"管理员删除关键词: {keyword}")

    @filter.command("监控词列表", permission_type=filter.PermissionType.ADMIN)
    async def list_keywords(self, event: AstrMessageEvent):
        sender_qq = event.get_sender_id()
        if str(sender_qq) != str(self.admin_qq):
            yield event.plain_result("❌ 权限不足！仅管理员可使用此命令")
            return
        
        if not self.keywords:
            yield event.plain_result("🔍 当前没有监控关键词")
        else:
            keywords_list = "\n".join([f"• {kw}" for kw in self.keywords])
            yield event.plain_result(f"📝 监控词列表：\n{keywords_list}")

    @filter.command("添加监控群", permission_type=filter.PermissionType.ADMIN)
    async def add_monitor_group(self, event: AstrMessageEvent, group_id: str = None):
        sender_qq = event.get_sender_id()
        if str(sender_qq) != str(self.admin_qq):
            yield event.plain_result("❌ 权限不足！仅管理员可使用此命令")
            return
        
        if not group_id or not re.match(r"^\d+$", group_id):
            yield event.plain_result("❌ 用法：添加监控群 [纯数字群号]")
            return
        
        if group_id in self.white_list:
            yield event.plain_result(f"❌ 群 {group_id} 已在监控列表中")
        else:
            self.white_list.append(group_id)
            self.save_config()
            yield event.plain_result(f"✅ 已添加监控群：{group_id}")
            logger.info(f"管理员添加监控群: {group_id}")

    @filter.command("删除监控群", permission_type=filter.PermissionType.ADMIN)
    async def del_monitor_group(self, event: AstrMessageEvent, group_id: str = None):
        sender_qq = event.get_sender_id()
        if str(sender_qq) != str(self.admin_qq):
            yield event.plain_result("❌ 权限不足！仅管理员可使用此命令")
            return
        
        if not group_id:
            yield event.plain_result("❌ 用法：删除监控群 [群号]")
            return
        
        if group_id not in self.white_list:
            yield event.plain_result(f"❌ 群 {group_id} 不在监控列表中")
        else:
            self.white_list.remove(group_id)
            self.save_config()
            yield event.plain_result(f"✅ 已移除监控群：{group_id}")
            logger.info(f"管理员移除监控群: {group_id}")

    @filter.command("监控群列表", permission_type=filter.PermissionType.ADMIN)
    async def list_monitor_groups(self, event: AstrMessageEvent):
        sender_qq = event.get_sender_id()
        if str(sender_qq) != str(self.admin_qq):
            yield event.plain_result("❌ 权限不足！仅管理员可使用此命令")
            return
        
        if not self.white_list:
            yield event.plain_result("🔍 当前没有监控群")
        else:
            groups_list = "\n".join([f"• {g}" for g in self.white_list])
            yield event.plain_result(f"📝 监控群列表：\n{groups_list}")

    # 在admin_commands中添加测试命令
    @filter.command("test_alert")
    async def test_alert(self, event: AstrMessageEvent):
        """测试警报发送功能"""
        await self.send_private_alert(event, "这是一条测试警报消息")
        yield event.plain_result("已发送测试警报，请检查管理员QQ")
    
    async def send_private_alert(self, event: AstrMessageEvent, message: str):
        """发送私聊通知给管理员 - 使用context主动发送消息"""
        try:
            if not self.admin_qq or not self.admin_qq.isdigit():
                logger.error("管理员QQ号无效（为空或非数字）")
                return
            # 1. 构建管理员私聊的唯一标识符（unified_msg_origin）
            # 格式：平台名称:消息类型:管理员QQ号
            admin_unified_msg_origin = f"aiocqhttp:{MessageType.FRIEND_MESSAGE.value}:{self.admin_qq}"
            
            # 2. 构建消息链（包含警报文本）
            message_chain = MessageChain([Plain(text=message)])
            
            # 3. 使用context的send_message主动发送到管理员私聊
            # 该方法需传入目标会话标识和消息链
            success = await self.context.send_message(admin_unified_msg_origin, message_chain)
            
            if success:
                logger.info(f"已向管理员 {self.admin_qq} 发送私聊警报")
            else:
                logger.error(f"发送私聊警报失败，未找到管理员会话")
                
        except Exception as e:
            logger.error(f"发送私聊通知失败: {str(e)}")
           

    async def terminate(self):
        """插件卸载时执行"""
        logger.info("关键词监控插件已卸载")
