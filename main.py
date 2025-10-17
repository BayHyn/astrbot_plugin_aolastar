import aiohttp
import re
import time
import asyncio
from typing import Optional, Dict, Any, List
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 导入加解密功能
from .deencrypt import process_decrypt, process_encrypt
# 导入属性查询功能
from .attr import (
    get_attributes_list, 
    get_attribute_relations, 
    format_attributes_list, 
    format_attribute_relations,
    generate_attribute_image
)

@register("aolastar", "vmoranv", "奥拉星游戏内容解析插件", "1.0.3")
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
                headers={"User-Agent": "AstrBot-Aolastar-Plugin/1.0.3"}
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
                logger.error(f"API 请求失败: {response.status} - {url}")
                return None
        except Exception as e:
            logger.error(f"API 请求异常: {e}")
            return None

    @filter.command("ar_help")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """🎮 奥拉星封包查询插件

📋 封包查询命令:
• /ar_help - 显示此帮助信息
• /ar_existingpacket - 获取现有封包列表（默认显示前20个）
• /ar_existingpacket next - 显示下20个封包
• /ar_existingpacket prev - 显示上20个封包
• /ar_existingpacket <名称> - 搜索包含指定名称的封包
• /ar_existingpacket refresh - 强制刷新封包数据缓存

🔐 加解密命令:
• /ar_decrypt <Base64内容> - 将Base64内容解密为JSON格式
• /ar_encrypt <JSON内容> - 将JSON内容加密为Base64格式

🔮 属性查询命令:
• /ar_attr ls - 列出所有属性系别
• /ar_attr <属性ID> - 查看特定属性的克制关系
• /ar_attr_image <属性ID> - 生成特定属性的克制关系图

🐾 亚比查询命令:
• /ar_pet_search <关键词> - 根据关键词搜索亚比
• /ar_pet_query <ID> - 根据ID查询单个亚比信息
• /ar_pet_query <ID1,ID2,ID3> - 根据多个ID查询亚比信息（逗号分隔）

🔄 亚比交换解析命令:
• /ar_exchange <userid> - 解析亚比交换信息（直接输入userid数字）
• /ar_exchange <链接> - 解析亚比交换信息（从链接中提取userid）

⚙️ 配置说明:
请在插件配置中设置 API 基础地址

⚠️ 安全说明:
搜索功能使用安全的字符串匹配，每个用户的分页状态独立存储

📖 更多信息请查看项目文档"""
        
        yield event.plain_result(help_text)

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
            packet_preview = f"{packet[:50]}..." if len(packet) > 50 else packet
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
            message_lines.extend([
                f"{i + 1}. {name}",
                f"   封包: {packet}",
                ""
            ])
        
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
        elif len(result) > 2000:
            truncated_result = f"{result[:2000]}\n\n⚠️ 结果过长，已截取显示前2000个字符"
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
        elif len(result) > 2000:
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

    @filter.command("ar_attr")
    async def attribute_command(self, event: AstrMessageEvent):
        """属性查询命令"""
        if not self.api_base_url:
            yield event.plain_result("❌ API 基础地址未配置，请在插件设置中配置")
            return
        
        # 解析命令参数
        args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
        
        if not args:
            yield event.plain_result("❌ 请提供属性查询参数\n用法: /ar_attr ls (列出所有属性) 或 /ar_attr <属性ID> (查看属性克制关系)")
            return
        
        if args[0].lower() == "ls":
            # 列出所有属性
            yield event.plain_result("🔄 正在获取属性列表...")
            
            attributes = await get_attributes_list(self)
            if not attributes:
                yield event.plain_result("❌ 获取属性列表失败，请检查网络连接或API地址配置")
                return
            
            result = format_attributes_list(attributes)
            yield event.plain_result(result)
            return
            
        # 查询特定属性的克制关系
        try:
            attr_id = int(args[0])
        except ValueError:
            yield event.plain_result("❌ 请输入有效的属性ID\n用法: /ar_attr <属性ID>")
            return
        
        yield event.plain_result("🔄 正在获取属性克制关系...")
        
        # 获取属性列表以获取属性名称
        attributes = await get_attributes_list(self)
        if not attributes:
            yield event.plain_result("❌ 获取属性列表失败，请检查网络连接或API地址配置")
            return
        
        # 查找指定ID的属性
        target_attr = next((attr for attr in attributes if attr["id"] == attr_id), None)
        if not target_attr:
            yield event.plain_result(f"❌ 未找到ID为 {attr_id} 的属性")
            return
        
        # 获取属性克制关系
        relations = await get_attribute_relations(self, attr_id)
        if not relations:
            yield event.plain_result(f"❌ 获取 {target_attr['name']} 属性的克制关系失败")
            return
        
        # 预加载所有属性的关系数据，确保防御逻辑能够正确工作
        logger.info("[DEBUG] 预加载所有属性的关系数据以支持防御分析")
        for attr in attributes:
            other_attr_id = attr["id"]
            if other_attr_id != attr_id:  # 跳过已经加载的当前属性
                await get_attribute_relations(self, other_attr_id)
        
        logger.info("[DEBUG] 所有属性关系数据预加载完成，开始格式化属性关系")
        result = format_attribute_relations(attr_id, target_attr["name"], relations, attributes)
        yield event.plain_result(result)

    @filter.command("ar_attr_image")
    async def attribute_image_command(self, event: AstrMessageEvent):
        """属性克制关系图生成命令"""
        if not self.api_base_url:
            yield event.plain_result("❌ API 基础地址未配置，请在插件设置中配置")
            return
        
        # 解析命令参数
        args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
        
        if not args:
            yield event.plain_result("❌ 请提供属性ID\n用法: /ar_attr_image <属性ID>")
            return
        
        try:
            attr_id = int(args[0])
        except ValueError:
            yield event.plain_result("❌ 请输入有效的属性ID\n用法: /ar_attr_image <属性ID>")
            return
            
        yield event.plain_result("🔄 正在生成属性克制关系图...")
        
        # 获取属性列表
        attributes = await get_attributes_list(self)
        if not attributes:
            yield event.plain_result("❌ 获取属性列表失败，请检查网络连接或API地址配置")
            return
        
        # 查找指定ID的属性
        target_attr = next((attr for attr in attributes if attr["id"] == attr_id), None)
        if not target_attr:
            yield event.plain_result(f"❌ 未找到ID为 {attr_id} 的属性")
            return
        
        # 获取属性克制关系
        relations = await get_attribute_relations(self, attr_id)
        if not relations:
            yield event.plain_result(f"❌ 获取 {target_attr['name']} 属性的克制关系失败")
            return
        
        # 预加载所有属性的关系数据，确保防御逻辑能够正确工作
        logger.info("[DEBUG] 预加载所有属性的关系数据以支持防御分析（图片生成）")
        for attr in attributes:
            other_attr_id = attr["id"]
            if other_attr_id != attr_id:  # 跳过已经加载的当前属性
                await get_attribute_relations(self, other_attr_id)
        
        logger.info("[DEBUG] 所有属性关系数据预加载完成，开始生成属性关系图")
        # 生成图片
        try:
            image_bytes = await generate_attribute_image(attr_id, target_attr["name"], relations, attributes)
            # 使用MessageChain发送图片
            try:
                from astrbot.api.message_components import Plain, Image
                chain = [
                    Plain(f"{target_attr['name']} 属性的克制关系图：\n"),
                    Image.fromBytes(image_bytes)
                ]
                yield event.chain_result(chain)
            except ImportError:
                # Fallback to plain text if message components are not available
                yield event.plain_result(f"✅ {target_attr['name']} 属性的克制关系图已生成，但当前平台不支持图片显示")
        except Exception as e:
            yield event.plain_result(f"❌ 生成属性克制关系图失败: {str(e)}")

    @filter.command("ar_exchange")
    async def exchange_command(self, event: AstrMessageEvent):
        """亚比交换解析命令"""
        if not self.api_base_url:
            yield event.plain_result("❌ API 基础地址未配置，请在插件设置中配置")
            return
        
        # 解析消息内容，提取userid
        message_text = event.message_str
        userid = (userid_match[1]) if (userid_match := re.search(r'userid=(\d+)', message_text)) else None
        if not userid:
            # 尝试直接获取数字UID
            args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
            if not args:
                yield event.plain_result("❌ 请提供userid或包含userid的链接\n用法: /ar_exchange <userid> 或 /ar_exchange <链接>")
                return
            
            # 检查第一个参数是否为纯数字
            if not args[0].isdigit():
                yield event.plain_result("❌ 请输入有效的userid（数字）或包含userid的链接\n用法: /ar_exchange <userid> 或 /ar_exchange <链接>")
                return
            userid = args[0]
        
        logger.info(f"提取到userid: {userid}")
        
        yield event.plain_result("🔄 正在解析亚比交换信息...")
        
        # 构建API请求URL
        api_url = f"{self.api_base_url}/api/extract-petid"
        
        # 根据OpenAPI规范准备请求数据，使用keyword字段
        request_data = {"keyword": userid}
        
        try:
            # 发送POST请求
            if not self.session:
                yield event.plain_result("❌ HTTP会话未初始化")
                return
            async with self.session.post(api_url, json=request_data) as response:
                # 记录详细的响应信息用于调试
                response_text = await response.text()
                logger.info(f"API响应状态: {response.status}, 响应内容: {response_text}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        formatted_result = self._format_petid_result(result)
                        yield event.plain_result(formatted_result)
                    except Exception as e:
                        logger.error(f"JSON解析错误: {e}")
                        yield event.plain_result(f"❌ 响应解析错误: {response_text}")
                else:
                    error_msg = f"❌ API请求失败，状态码: {response.status}, 错误信息: {response_text}"
                    logger.error(error_msg)
                    
                    # 如果是400错误，尝试使用userIdList格式（兼容旧版本）
                    if response.status == 400:
                        logger.info("尝试使用userIdList格式进行兼容请求")
                        request_data_compat = {"userIdList": [userid]}
                        if not self.session:
                            yield event.plain_result("❌ HTTP会话未初始化")
                            return
                        async with self.session.post(api_url, json=request_data_compat) as response2:
                            response2_text = await response2.text()
                            logger.info(f"兼容请求响应状态: {response2.status}, 响应内容: {response2_text}")
                            
                            if response2.status == 200:
                                try:
                                    result = await response2.json()
                                    formatted_result = self._format_petid_result(result)
                                    yield event.plain_result(formatted_result)
                                except Exception as e:
                                    logger.error(f"JSON解析错误: {e}")
                                    yield event.plain_result(f"❌ 响应解析错误: {response2_text}")
                            else:
                                error_msg = f"❌ API请求失败（兼容格式），状态码: {response2.status}, 错误信息: {response2_text}"
                                logger.error(error_msg)
                                yield event.plain_result("❌ API端点调用错误，请确认后端服务是否正确配置了/extract-petid端点")
                    else:
                        yield event.plain_result(error_msg)
        except Exception as e:
            error_msg = f"❌ 解析亚比交换信息时发生错误: {str(e)}"
            logger.error(error_msg)
            yield event.plain_result(error_msg)

    @filter.regex(r'https?://www\.100bt\.com/aola/act/zt-friend/\?userid=\d+')
    async def auto_extract_petid(self, event: AstrMessageEvent):
        """自动监听并解析奥拉星好友链接"""
        if not self.api_base_url:
            return  # API未配置时静默跳过
            
        message_text = event.message_str
        if (userid_match := re.search(r'userid=(\d+)', message_text)):
            userid = userid_match[1]
            logger.info(f"自动提取到userid: {userid}")
            
            # 构建API请求URL
            api_url = f"{self.api_base_url}/api/extract-petid"
            
            # 根据OpenAPI规范准备请求数据，使用keyword字段
            request_data = {"keyword": userid}
            
            try:
                # 发送POST请求
                if not self.session:
                    logger.error("HTTP会话未初始化，无法自动解析")
                    return
                async with self.session.post(api_url, json=request_data) as response:
                    _ = await response.text()  # consume response but ignore content
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                            formatted_result = self._format_petid_result(result)
                            yield event.plain_result(formatted_result)
                        except Exception as e:
                            logger.error(f"JSON解析错误: {e}")
                            # 自动解析失败时不提示用户
                    elif response.status == 400:
                        # 尝试使用userIdList格式（兼容旧版本）
                        request_data_compat = {"userIdList": [userid]}
                        if not self.session:
                            logger.error("HTTP会话未初始化，无法自动解析")
                            return
                        async with self.session.post(api_url, json=request_data_compat) as response2:
                            if response2.status == 200:
                                try:
                                    result = await response2.json()
                                    formatted_result = self._format_petid_result(result)
                                    yield event.plain_result(formatted_result)
                                except Exception as e:
                                    logger.error(f"JSON解析错误: {e}")
                    else:
                        logger.error(f"自动解析API请求失败，状态码: {response.status}")
            except Exception as e:
                logger.error(f"自动解析亚比交换信息时发生错误: {str(e)}")

    @filter.command("ar_pet_search")
    async def pet_search_command(self, event: AstrMessageEvent):
        """根据关键词搜索亚比"""
        if not self.api_base_url:
            yield event.plain_result("❌ API 基础地址未配置，请在插件设置中配置")
            return
        
        # 解析命令参数
        args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
        
        if not args:
            yield event.plain_result("❌ 请提供搜索关键词\n用法: /ar_pet_search <关键词>")
            return
        
        keyword = " ".join(args)
        
        yield event.plain_result(f"🔄 正在搜索包含 '{keyword}' 的亚比...")
        
        # 构建API请求URL
        api_url = f"{self.api_base_url}/api/pets/search"
        
        # 根据OpenAPI规范准备请求数据
        request_data = {"keyword": keyword}
        
        try:
            # 发送POST请求
            if not self.session:
                yield event.plain_result("❌ HTTP会话未初始化")
                return
            async with self.session.post(api_url, json=request_data) as response:
                if response.status == 200:
                    try:
                        result = await response.json()
                        # 格式化搜索结果
                        formatted_result = self._format_pet_search_result(result, keyword)
                        yield event.plain_result(formatted_result)
                    except Exception as e:
                        logger.error(f"JSON解析错误: {e}")
                        yield event.plain_result("❌ 响应解析错误")
                else:
                    error_msg = f"❌ API请求失败，状态码: {response.status}"
                    logger.error(error_msg)
                    yield event.plain_result(error_msg)
        except Exception as e:
            error_msg = f"❌ 搜索亚比时发生错误: {str(e)}"
            logger.error(error_msg)
            yield event.plain_result(error_msg)

    @filter.command("ar_pet_query")
    async def pet_query_command(self, event: AstrMessageEvent):
        """根据ID查询亚比信息，支持单个或多个ID（逗号分隔）"""
        if not self.api_base_url:
            yield event.plain_result("❌ API 基础地址未配置，请在插件设置中配置")
            return
        
        # 解析命令参数
        args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
        
        if not args:
            yield event.plain_result("❌ 请提供亚比ID\n用法: /ar_pet_query <ID> 或 /ar_pet_query <ID1,ID2,ID3>")
            return
        
        # 解析ID列表
        id_input = " ".join(args)
        pet_ids = [pet_id.strip() for pet_id in id_input.split(",") if pet_id.strip().isdigit()]
        
        if not pet_ids:
            yield event.plain_result("❌ 请提供有效的亚比ID（纯数字）")
            return
        
        
        # 查询单个或多个亚比
        if len(pet_ids) == 1:
            result = await self._query_single_pet(pet_ids[0])
            formatted_result = self._format_pet_query_result(result, pet_ids[0])
            yield event.plain_result(formatted_result)
        else:
            CHUNK_SIZE = 20
            total_ids = len(pet_ids)
            yield event.plain_result(f"🔍 收到 {total_ids} 个亚比ID查询请求，将分批处理...")

            num_chunks = (total_ids + CHUNK_SIZE - 1) // CHUNK_SIZE
            for i in range(0, total_ids, CHUNK_SIZE):
                chunk_ids = pet_ids[i:i + CHUNK_SIZE]
                
                # 并发查询当前批次的亚比
                tasks = [self._query_single_pet(pet_id) for pet_id in chunk_ids]
                results_data = await asyncio.gather(*tasks)
                
                # 格式化结果
                results = []
                for pet_id, result in zip(chunk_ids, results_data):
                    formatted_result = self._format_pet_query_result(result, pet_id)
                    results.append(formatted_result)
                
                # 合并结果并发送
                combined_result = "\n\n".join(results)
                chunk_num = i // CHUNK_SIZE + 1
                yield event.plain_result(f"--- 批次 {chunk_num}/{num_chunks} ---\n{combined_result}")
                
                # 在批次之间添加延迟以避免速率限制
                if chunk_num < num_chunks:
                    await asyncio.sleep(1)

    async def _query_single_pet(self, pet_id: str) -> Dict[str, Any]:
        """查询单个亚比信息"""
        try:
            response = await self._make_request(f"/api/pet/{pet_id}")
            return response if response is not None else {"success": False, "error": "请求失败"}
        except Exception as e:
            logger.error(f"查询亚比 {pet_id} 时发生错误: {e}")
            return {"success": False, "error": str(e)}

    def _format_pet_query_result(self, result: Dict[str, Any], pet_id: str) -> str:
        """格式化亚比查询结果"""
        if not result or not result.get("success", False):
            return f"❌ ID {pet_id}: 未找到相关亚比信息"
        
        data = result.get("data", [])
        logger.info(f"[DEBUG] 亚比 {pet_id} 的原始数据: {data}")
        
        if not data or len(data) < 2:
            return f"❌ ID {pet_id}: 返回数据格式不正确"
        
        # 只提取ID和名称
        pet_name = data[1] if len(data) > 1 else "未知"
        
        message_lines = [
            f"🆔 亚比ID: {pet_id}",
            f"📛 名称: {pet_name}"
        ]
        
        return "\n".join(message_lines)

    def _format_pet_search_result(self, result: Dict[str, Any], keyword: str) -> str:
        """格式化亚比搜索结果"""
        if not result or "data" not in result:
            return "❌ 未获取到有效的搜索结果"
        
        data = result.get("data", [])
        if not data:
            return f"❌ 未找到包含 '{keyword}' 的亚比"
        
        message_lines = [f"🔍 找到 {len(data)} 个包含 '{keyword}' 的亚比:"]
        
        # 限制显示数量，避免信息过长
        display_count = min(len(data), 20)
        for i, pet in enumerate(data[:display_count], 1):
            pet_id = pet.get("id", "未知")
            pet_name = pet.get("name", "未知亚比")
            message_lines.append(f"{i}. {pet_name} (ID: {pet_id})")
        
        if len(data) > display_count:
            message_lines.append(f"\n⚠️ 结果过多，仅显示前 {display_count} 个")
        
        return "\n".join(message_lines)

    def _format_petid_result(self, result: Dict[str, Any]) -> str:
        """格式化亚比交换解析结果"""
        if not result or "results" not in result:
            return "❌ 未获取到有效的解析结果"
        
        results = result.get("results", [])
        if not results:
            return "❌ 未找到该用户的亚比交换信息"
        
        user_result = results[0]  # 取第一个结果
        userid = user_result.get("userid", "未知")
        success = user_result.get("success", False)
        _ = user_result.get("petIds", [])  # pet_ids is unused
        pet_infos = user_result.get("petInfos", [])
        raw_data = user_result.get("rawData", {})
        
        message_lines = [f"🔍 亚比交换解析结果 - 用户ID: {userid}"]
        
        if not success:
            message_lines.append("❌ 解析失败，可能用户不存在或没有交换记录")
            return "\n".join(message_lines)
        
        # 显示基本信息
        if (nn := raw_data.get("nn")):
            state = raw_data.get("state", 0)
            state_map = {0: "未知", 1: "正常", 2: "已交换"}
            state_str = state_map.get(state, "未知")
            message_lines.append(f"📛 用户名: {nn}")
            message_lines.append(f"📊 状态: {state_str}")
        
        # 显示宠物信息
        if pet_infos:
            message_lines.append("\n🎯 拥有的亚比:")
            for i, pet_info in enumerate(pet_infos, 1):
                name = pet_info.get("name", "未知亚比")
                pet_type = pet_info.get("type", "未知类型")  # Avoid shadowing built-in 'type'
                type_emoji = {"gold": "💰", "silver": "🥈", "copper": "🥉"}.get(pet_type, "❓")
                message_lines.append(f"{i}. {type_emoji} {name} ({pet_type})")
        
        # 显示交换记录
        if (logs := raw_data.get("logs")):
            self._format_exchange_logs(logs, message_lines)
        
        message_lines.append("\n💡 使用提示: 复制链接分享给其他玩家查看你的亚比交换信息")
        
        return "\n".join(message_lines)

    def _format_user_info(self, raw_data: Dict[str, Any], message_lines: List[str]) -> None:
        """格式化用户基本信息"""
        if (nn := raw_data.get("nn")):
            state = raw_data.get("state", 0)
            state_map = {0: "未知", 1: "正常", 2: "已交换"}
            state_str = state_map.get(state, "未知")
            message_lines.append(f"📛 用户名: {nn}")
            message_lines.append(f"📊 状态: {state_str}")

    def _format_exchange_logs(self, logs: List[Dict[str, Any]], message_lines: List[str]) -> None:
        """格式化交换记录"""
        message_lines.append("\n📋 最近交换记录:")
        for log in logs[:3]:  # 显示最近3条记录
            de = log.get("de", 0)
            re = log.get("re", "未知")
            ne = log.get("ne", "未知用户")
            # 转换时间戳为可读格式
            from datetime import datetime
            try:
                time_str = datetime.fromtimestamp(de / 1000).strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = "未知时间"
            message_lines.append(f"   ⏰ {time_str}: 与 {ne} 交换了宠物 {re}")

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