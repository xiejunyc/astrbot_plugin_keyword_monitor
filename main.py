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
        

    def save_config(self):
        """保存配置到文件"""
        try:
            config_data = {
                'keywords': self.keywords,
                'white_list': self.white_list,
                'admin_qq': self.admin_qq
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            logger.info("配置文件已保存")
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")

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

    @filter.command("km", permission_type=filter.PermissionType.ADMIN)
    async def admin_commands(self, event: AstrMessageEvent, action: str = None, param: str = None):
        """管理员命令入口"""
        #验证发送者是否为管理员QQ
        sender_qq = event.get_sender_id()

        if not self.admin_qq:
            yield event.plain_result("❌ 未设置管理员QQ，请联系开发者初始化")
            return

        if sender_qq != self.admin_qq:
            yield event.plain_result("❌ 权限不足！仅管理员可使用此命令")
            logger.warning(f"非管理员{sender_qq}尝试使用管理员命令")
            return
        
        # 如果没有提供命令或参数，显示帮助信息
        if not action:
            yield event.plain_result(
                "🔑 关键词监控管理命令 🔑\n"
                "----------------------\n"
                "1. 添加关键词: /km add_key [关键词]\n"
                "2. 删除关键词: /km del_key [关键词]\n"
                "3. 列出关键词: /km list_keys\n"
                "4. 添加白名单群: /km add_group [群号]\n"
                "5. 删除白名单群: /km del_group [群号]\n"
                "6. 列出白名单: /km list_groups\n"
                "7. 设置管理员QQ: /km set_admin [QQ号]\n"
            )
            return
        
        action = action.lower()  # 统一转为小写，避免大小写问题
        param_str = str(param) if param is not None else None
        
        # 根据命令类型直接处理逻辑
        if action == "add_key" and param:
            # 添加关键词
            if param in self.keywords:
                yield event.plain_result(f"❌ 关键词 '{param}' 已存在")
            else:
                self.keywords.append(param)
                self.save_config()
                yield event.plain_result(f"✅ 已添加关键词: {param}")
                logger.info(f"管理员添加关键词: {param}")
        
        elif action == "del_key" and param:
            # 删除关键词
            if param not in self.keywords:
                yield event.plain_result(f"❌ 关键词 '{param}' 不存在")
            else:
                self.keywords.remove(param)
                self.save_config()
                yield event.plain_result(f"✅ 已删除关键词: {param}")
                logger.info(f"管理员删除关键词: {param}")
        
        elif action == "list_keys":
            # 列出所有关键词
            if not self.keywords:
                yield event.plain_result("🔍 当前没有监控关键词")
            else:
                keywords_list = "\n".join([f"• {kw}" for kw in self.keywords])
                yield event.plain_result(f"📝 监控关键词列表:\n{keywords_list}")
        
        elif action == "add_group" and param:
            # 添加白名单群
            if not re.match(r"^\d+$", param_str):
                yield event.plain_result("❌ 群号必须是纯数字")
            elif param_str in self.white_list:
                yield event.plain_result(f"❌ 群 {param_str} 已在白名单中")
            else:
                self.white_list.append(param_str)
                self.save_config()
                yield event.plain_result(f"✅ 已添加白名单群: {param_str}")
                logger.info(f"管理员添加白名单群: {param_str}")
        
        elif action == "del_group" and param:
            # 删除白名单群
            if param_str not in self.white_list:
                yield event.plain_result(f"❌ 群 {param_str} 不在白名单中")
            else:
                self.white_list.remove(param_str)
                self.save_config()
                yield event.plain_result(f"✅ 已移除白名单群: {param_str}")
                logger.info(f"管理员移除白名单群: {param_str}")
        
        elif action == "list_groups":
            # 列出白名单群
            if not self.white_list:
                yield event.plain_result("🔍 当前没有白名单群")
            else:
                groups_list = "\n".join([f"• {group}" for group in self.white_list])
                yield event.plain_result(f"📝 白名单群列表:\n{groups_list}")
        
        elif action == "set_admin" and param:
            # 设置管理员QQ
            if not re.match(r"^\d{5,12}$", param_str):
                yield event.plain_result("❌ 无效的QQ号格式")
            else:
                self.admin_qq = param_str
                self.save_config()
                yield event.plain_result(f"✅ 管理员QQ已设置为: {param_str}")
                logger.info(f"管理员QQ更新为: {param_str}")
        
        else:
            yield event.plain_result("❌ 无效命令或参数，请使用 /km 查看帮助")

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
