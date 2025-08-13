import aiohttp
import re
from typing import Optional, Dict, Any, List
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("aolastar", "vmoranv", "奥拉星游戏内容解析插件", "1.0.0")
class AolastarPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.api_base_url: str = ""
        self.session: Optional[aiohttp.ClientSession] = None
        self.current_page: int = 0  # 当前页码
        self.cached_activities: Optional[List[Dict[str, Any]]] = None  # 缓存的活动列表

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
        help_text = """🎮 奥拉星游戏内容解析插件

📋 可用命令:
• /ar_help - 显示此帮助信息
• /ar_existingpacket - 获取现有封包列表（默认显示前20个）
• /ar_existingpacket next - 显示下20个封包
• /ar_existingpacket prev - 显示上20个封包
• /ar_existingpacket <名称> - 搜索匹配名称的封包

⚙️ 配置说明:
请在插件配置中设置 API 基础地址

📖 更多信息请查看项目文档"""
        
        yield event.plain_result(help_text)

    async def _get_activities_data(self) -> Optional[List[Dict[str, Any]]]:
        """获取活动数据，使用缓存机制"""
        if self.cached_activities is None:
            result = await self._make_request("/api/existing-activities")
            if result and isinstance(result, list):
                self.cached_activities = result
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
        try:
            # 使用正则表达式进行模糊匹配
            pattern = re.compile(search_name, re.IGNORECASE)
            matched_activities = []
            
            for activity in activities:
                name = activity.get("name", "")
                if pattern.search(name):
                    matched_activities.append(activity)
            
            if not matched_activities:
                return f"❌ 未找到匹配 '{search_name}' 的封包"
            
            message_lines = [f"🔍 找到 {len(matched_activities)} 个匹配 '{search_name}' 的封包:\n"]
            
            for i, activity in enumerate(matched_activities):
                name = activity.get("name", "未知活动")
                packet = activity.get("packet", "")
                message_lines.append(f"{i + 1}. {name}")
                message_lines.append(f"   封包: {packet}")
                message_lines.append("")
            
            return "\n".join(message_lines)
            
        except re.error:
            return f"❌ 搜索模式 '{search_name}' 无效，请检查正则表达式语法"

    @filter.command("ar_existingpacket")
    async def existing_activities_command(self, event: AstrMessageEvent):
        """获取现有封包列表"""
        if not self.api_base_url:
            yield event.plain_result("❌ API 基础地址未配置，请在插件设置中配置")
            return
        
        # 解析命令参数
        args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
        
        yield event.plain_result("🔄 正在获取现有封包列表...")
        
        # 获取活动数据
        activities = await self._get_activities_data()
        if not activities:
            yield event.plain_result("❌ 获取封包列表失败，请检查 API 地址是否正确")
            return
        
        max_display = 20
        
        if not args:
            # 默认显示第一页
            self.current_page = 0
            result = self._format_activity_list(activities, 0, max_display)
            yield event.plain_result(result)
            
        elif args[0].lower() == "next":
            # 显示下一页
            next_start = (self.current_page + 1) * max_display
            if next_start < len(activities):
                self.current_page += 1
                result = self._format_activity_list(activities, next_start, max_display)
                yield event.plain_result(result)
            else:
                yield event.plain_result("❌ 已经是最后一页了")
                
        elif args[0].lower() == "prev":
            # 显示上一页
            if self.current_page > 0:
                self.current_page -= 1
                prev_start = self.current_page * max_display
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
        except Exception as e:
            logger.error(f"奥拉星插件销毁时出错: {e}")