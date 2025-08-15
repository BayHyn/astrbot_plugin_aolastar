import aiohttp
import re
import time
from typing import Optional, Dict, Any, List
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 导入加解密功能
from .deencrypt import process_decrypt, process_encrypt

@register("aolastar", "vmoranv", "奥拉星游戏内容解析插件", "1.0.0")
class AolastarPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.api_base_url: str = ""
        self.session: Optional[aiohttp.ClientSession] = None
        # 修复1: 使用会话级别的分页状态，避免多用户间的状态共享
        self.user_page_states: Dict[str, int] = {}  # 存储每个会话的当前页码
        # 修复2: 添加缓存失效机制
        self.cached_activities: Optional[List[Dict[str, Any]]] = None
        self.cache_timestamp: float = 0  # 缓存时间戳
        self.cache_ttl: int = 300  # 缓存有效期5分钟

    async def initialize(self):
        """插件初始化"""
        try:
            # 从构造函数传入的 config 获取配置
            logger.info(f"奥拉星插件: 读取到的配置: {self.config}")
            
            self.api_base_url = self.config.get("api_base_url", "").rstrip("/")
            logger.info(f"奥拉星插件: 解析的API地址: '{self.api_base_url}'")
            
            if not self.api_base_url:
                logger.warning("奥拉星插件: API 基础地址未配置")
                return
            
            # 添加协议前缀
            if not self.api_base_url.startswith(('http://', 'https://')):
                self.api_base_url = f"http://{self.api_base_url}"
                logger.info(f"奥拉星插件: 添加协议前缀后的API地址: {self.api_base_url}")
            
            # 创建 HTTP 会话
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "AstrBot-Aolastar-Plugin/1.0.0"}
            )
            
            logger.info(f"奥拉星插件初始化成功，API 地址: {self.api_base_url}")
            
        except Exception as e:
            logger.error(f"奥拉星插件初始化失败: {e}")

    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """发送 API 请求"""
        if not self.session or not self.api_base_url:
            return None
            
        try:
            url = f"{self.api_base_url}{endpoint}"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API 请求失败: {response.status} - {url}")
                    return None
        except Exception as e:
            logger.error(f"API 请求异常: {e}")
            return None

    @filter.command("ar_help")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """🎮 奥拉星封包查询插件

📋 可用命令:
• /ar_help - 显示此帮助信息
• /ar_existingpacket - 获取现有封包列表（默认显示前20个）
• /ar_existingpacket next - 显示下20个封包
• /ar_existingpacket prev - 显示上20个封包
• /ar_existingpacket <名称> - 搜索包含指定名称的封包
• /ar_existingpacket refresh - 强制刷新封包数据缓存

⚙️ 配置说明:
请在插件配置中设置 API 基础地址

� 安全说明:
搜索功能使用安全的字符串匹配，每个用户的分页状态独立存储

📖 更多信息请查看项目文档"""
        
        # 更新帮助文本
        updated_help_text = help_text.replace(
            "📋 可用命令:",
            """📋 封包查询命令:"""
        ).replace(
            "📖 更多信息请查看项目文档",
            """🔐 加解密命令:
• /ar_decrypt <Base64内容> - 将Base64内容解密为JSON格式
• /ar_encrypt <JSON内容> - 将JSON内容加密为Base64格式

📖 更多信息请查看项目文档"""
        )
        
        yield event.plain_result(updated_help_text)

    async def _get_activities_data(self, force_refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
        """获取活动数据，使用带失效机制的缓存"""
        current_time = time.time()
        
        # 检查缓存是否需要刷新
        cache_expired = (current_time - self.cache_timestamp) > self.cache_ttl
        
        if force_refresh or self.cached_activities is None or cache_expired:
            logger.info("正在刷新封包数据缓存...")
            result = await self._make_request("/api/existing-activities")
            if result and isinstance(result, list):
                self.cached_activities = result
                self.cache_timestamp = current_time
                logger.info(f"缓存已更新，获取到 {len(result)} 个封包")
            else:
                logger.warning("获取封包数据失败，使用旧缓存数据")
        
        return self.cached_activities

    def _format_activity_list(self, activities: List[Dict[str, Any]], start_index: int = 0, max_display: int = 20) -> str:
        """格式化活动列表显示"""
        if not activities:
            return "📭 暂无可用的封包列表"
        
        end_index = min(start_index + max_display, len(activities))
        display_activities = activities[start_index:end_index]
        
        message_lines = [f"✅ 找到 {len(activities)} 个封包，显示第 {start_index + 1}-{end_index} 个:\n"]
        
        for i, activity in enumerate(display_activities):
            name = activity.get("name", "未知活动")
            packet = activity.get("packet", "")
            # 截取封包信息的前50个字符
            packet_preview = packet[:50] + "..." if len(packet) > 50 else packet
            message_lines.append(f"{start_index + i + 1}. {name}")
            if packet_preview:
                message_lines.append(f"   封包: {packet_preview}")
            message_lines.append("")
        
        # 添加分页信息
        current_page = start_index // max_display + 1
        total_pages = (len(activities) + max_display - 1) // max_display
        message_lines.append(f"📄 第 {current_page}/{total_pages} 页")
        
        if start_index + max_display < len(activities):
            message_lines.append("💡 使用 /ar_existingpacket next 查看下一页")
        if start_index > 0:
            message_lines.append("💡 使用 /ar_existingpacket prev 查看上一页")
        
        return "\n".join(message_lines)

    def _search_activities(self, activities: List[Dict[str, Any]], search_name: str) -> str:
        """搜索匹配的活动"""
        # 修复3: 防止正则表达式拒绝服务攻击，使用安全的字符串匹配
        matched_activities = []
        
        # 将搜索词转换为小写以进行不区分大小写的搜索
        search_lower = search_name.lower()
        
        # 限制搜索词长度，防止过长的输入
        if len(search_name) > 100:
            return "❌ 搜索词过长，请使用较短的关键词"
        
        for activity in activities:
            name = activity.get("name", "")
            # 使用安全的字符串包含匹配，而不是正则表达式
            if search_lower in name.lower():
                matched_activities.append(activity)
        
        if not matched_activities:
            return f"❌ 未找到包含 '{search_name}' 的封包"
        
        # 限制搜索结果数量，避免消息过长
        max_results = 50
        if len(matched_activities) > max_results:
            matched_activities = matched_activities[:max_results]
            truncated_msg = f"\n⚠️ 结果过多，仅显示前 {max_results} 个"
        else:
            truncated_msg = ""
        
        message_lines = [f"🔍 找到 {len(matched_activities)} 个包含 '{search_name}' 的封包:{truncated_msg}\n"]
        
        for i, activity in enumerate(matched_activities):
            name = activity.get("name", "未知活动")
            packet = activity.get("packet", "")
            message_lines.append(f"{i + 1}. {name}")
            message_lines.append(f"   封包: {packet}")
            message_lines.append("")
        
        return "\n".join(message_lines)



    @filter.command("ar_decrypt")
    async def decrypt_command(self, event: AstrMessageEvent):
        """Base64解密命令"""
        args = event.message_str.split(maxsplit=1)
        
        if len(args) < 2:
            yield event.plain_result("❌ 请提供要解密的Base64内容\n用法: /ar_decrypt <Base64内容>")
            return
        
        base64_content = args[1].strip()
        
        # 限制输入长度，防止过大的数据
        if len(base64_content) > 10000:
            yield event.plain_result("❌ 输入内容过长，请使用较短的Base64内容（最大10000字符）")
            return
        
        if not base64_content:
            yield event.plain_result("❌ Base64内容不能为空")
            return
        
        yield event.plain_result("🔄 正在解密Base64内容...")
        
        result = process_decrypt(base64_content)
        
        # 处理结果显示
        if result.startswith("错误：") or result.startswith("解密错误:"):
            yield event.plain_result(f"❌ {result}")
        else:
            # 如果结果太长，截取显示
            if len(result) > 2000:
                truncated_result = result[:2000] + "\n\n⚠️ 结果过长，已截取显示前2000个字符"
                yield event.plain_result(f"✅ 解密成功:\n```json\n{truncated_result}\n```")
            else:
                yield event.plain_result(f"✅ 解密成功:\n```json\n{result}\n```")

    @filter.command("ar_encrypt")
    async def encrypt_command(self, event: AstrMessageEvent):
        """JSON加密命令"""
        args = event.message_str.split(maxsplit=1)
        
        if len(args) < 2:
            yield event.plain_result("❌ 请提供要加密的JSON内容\n用法: /ar_encrypt <JSON内容>")
            return
        
        json_content = args[1].strip()
        
        # 限制输入长度，防止过大的数据
        if len(json_content) > 10000:
            yield event.plain_result("❌ 输入内容过长，请使用较短的JSON内容（最大10000字符）")
            return
        
        if not json_content:
            yield event.plain_result("❌ JSON内容不能为空")
            return
        
        yield event.plain_result("🔄 正在加密JSON内容...")
        
        result = process_encrypt(json_content)
        
        # 处理结果显示
        if result.startswith("错误：") or result.startswith("加密错误:"):
            yield event.plain_result(f"❌ {result}")
        else:
            # 如果结果太长，分段显示
            if len(result) > 2000:
                yield event.plain_result(f"✅ 加密成功:\n```\n{result[:2000]}\n```\n⚠️ 结果过长，已截取显示前2000个字符")
            else:
                yield event.plain_result(f"✅ 加密成功:\n```\n{result}\n```")

    @filter.command("ar_existingpacket")
    async def existing_activities_command(self, event: AstrMessageEvent):
        """获取现有封包列表"""
        if not self.api_base_url:
            yield event.plain_result("❌ API 基础地址未配置，请在插件设置中配置")
            return
        
        # 获取会话ID，用于区分不同用户的分页状态
        session_id = event.session_id
        
        # 解析命令参数
        args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
        
        # 检查是否需要强制刷新缓存
        force_refresh = len(args) > 0 and args[0].lower() == "refresh"
        if force_refresh:
            args = args[1:]  # 移除 refresh 参数
        
        yield event.plain_result("🔄 正在获取现有封包列表...")
        
        # 获取活动数据
        activities = await self._get_activities_data(force_refresh=force_refresh)
        if not activities:
            yield event.plain_result("❌ 获取封包列表失败，请检查 API 地址是否正确")
            return
        
        max_display = 20
        
        # 获取当前用户的分页状态
        current_page = self.user_page_states.get(session_id, 0)
        
        if not args:
            # 默认显示第一页
            current_page = 0
            self.user_page_states[session_id] = current_page
            result = self._format_activity_list(activities, 0, max_display)
            yield event.plain_result(result)
            
        elif args[0].lower() == "next":
            # 显示下一页
            next_start = (current_page + 1) * max_display
            if next_start < len(activities):
                current_page += 1
                self.user_page_states[session_id] = current_page
                result = self._format_activity_list(activities, next_start, max_display)
                yield event.plain_result(result)
            else:
                yield event.plain_result("❌ 已经是最后一页了")
                
        elif args[0].lower() == "prev":
            # 显示上一页
            if current_page > 0:
                current_page -= 1
                self.user_page_states[session_id] = current_page
                prev_start = current_page * max_display
                result = self._format_activity_list(activities, prev_start, max_display)
                yield event.plain_result(result)
            else:
                yield event.plain_result("❌ 已经是第一页了")
                
        else:
            # 搜索匹配的活动
            search_name = " ".join(args)
            result = self._search_activities(activities, search_name)
            yield event.plain_result(result)

    async def terminate(self):
        """插件销毁"""
        try:
            if self.session:
                await self.session.close()
                logger.info("奥拉星插件会话已关闭")
            
            # 清理用户状态数据
            self.user_page_states.clear()
            self.cached_activities = None
            logger.info("奥拉星插件状态数据已清理")
            
        except Exception as e:
            logger.error(f"奥拉星插件销毁时出错: {e}")