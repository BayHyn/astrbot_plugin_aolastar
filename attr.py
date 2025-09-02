
import time
import io
import os
import platform
import math
import aiohttp
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont
from astrbot.api import logger

def load_font_with_fallback(size: int):
    """
    加载字体并支持fallback机制，优先级：
    1. macOS系统字体：/System/Library/Fonts/PingFang.ttc
    2. Linux中文字体：/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc
    3. 其他常见字体路径
    4. 最后使用ImageFont.load_default()
    """
    # 按优先级排序的字体路径列表
    font_paths = [
        # macOS系统字体
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Arial Unicode.ttf",
        
        # Linux中文字体
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        
        # Windows字体（如果存在）
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
    ]
    
    # 尝试加载字体
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                logger.info(f"尝试加载字体 {font_path} 失败: {e}")
                continue
    
    # 如果所有字体都加载失败，使用默认字体
    logger.info("所有字体加载失败，使用默认字体")
    return ImageFont.load_default()

# 缓存属性数据，避免频繁请求API
class AttrCache:
    def __init__(self):
        self.attributes: Optional[List[Dict[str, Any]]] = None
        self.attribute_relations: Dict[int, Dict[str, Any]] = {}
        self.attributes_timestamp: float = 0
        self.relations_timestamp: Dict[int, float] = {}
        # 创建图标缓存目录
        self.icon_cache_dir: str = "attribute_icons"  # 图标缓存目录
        if not os.path.exists(self.icon_cache_dir):
            os.makedirs(self.icon_cache_dir)
        # 使用正确的奥拉星属性图标URL规则
        self.icon_url_template: str = "https://aola.100bt.com/h5/petattribute/attribute{}.png"  # 原系图标URL模板
        self.super_icon_url_template: str = "https://aola.100bt.com/h5/petattribute/oldattribute{}.png"  # 超系图标URL模板
        self.unified_super_icon_url: str = "https://aola.100bt.com/h5/petattribute/attribute999.png"  # 超系统一图标URL
        self.unified_origin_icon_url: str = "https://aola.100bt.com/h5/petattribute/attribute1000.png"  # 原系统一图标URL
    
    def is_expired(self, timestamp: float) -> bool:
        # 移除缓存过期检查，因为图标不大，可以长期缓存
        return False
    
    async def get_attribute_icon(self, session: aiohttp.ClientSession, attr_id: int) -> Optional[Image.Image]:
        """获取属性图标"""
        # 创建图标缓存目录
        if not os.path.exists(self.icon_cache_dir):
            os.makedirs(self.icon_cache_dir)
            
        # 构建缓存文件路径
        icon_path = os.path.join(self.icon_cache_dir, f"{attr_id}.png")
        
        # 如果缓存存在，直接返回
        if os.path.exists(icon_path):
            try:
                return Image.open(icon_path)
            except Exception as e:
                logger.info(f"打开缓存的属性图标失败: {e}")
                os.remove(icon_path)  # 删除损坏的缓存文件
        
        # 构建图标URL - 根据ID范围判断使用哪种URL模板
        if attr_id == 999:  # 超系统一图标
            icon_url = self.unified_super_icon_url
        elif attr_id == 1000:  # 原系统一图标
            icon_url = self.unified_origin_icon_url
        elif attr_id > 22:  # 超系图标
            icon_url = self.super_icon_url_template.format(attr_id)
        else:  # 原系图标
            icon_url = self.icon_url_template.format(attr_id)
        
        # 通过网络请求获取图标
        try:
            async with session.get(icon_url) as response:
                if response.status == 200:
                    content = await response.read()
                    # 保存到缓存
                    with open(icon_path, "wb") as f:
                        f.write(content)
                    # 返回图片对象
                    return Image.open(io.BytesIO(content))
                else:
                    logger.info(f"获取属性图标失败，状态码: {response.status}, URL: {icon_url}")
                    return None
        except Exception as e:
            logger.info(f"获取属性图标失败: {e}")
            return None

attr_cache = AttrCache()

async def get_attributes_list(plugin_instance) -> Optional[List[Dict[str, Any]]]:
    """获取属性列表"""
    current_time = time.time()
    
    # 检查缓存是否有效
    if attr_cache.attributes and not attr_cache.is_expired(attr_cache.attributes_timestamp):
        return attr_cache.attributes
    
    # 请求API获取数据
    result = await plugin_instance._make_request("/api/skill-attributes")
    if result and result.get("success"):
        attr_cache.attributes = result["data"]
        attr_cache.attributes_timestamp = current_time
        return attr_cache.attributes
    
    return None

async def get_attribute_relations(plugin_instance, attr_id: int) -> Optional[Dict[str, Any]]:
    """获取特定属性的克制关系"""
    current_time = time.time()
    
    # 检查缓存是否有效
    if (attr_id in attr_cache.attribute_relations and
        not attr_cache.is_expired(attr_cache.relations_timestamp.get(attr_id, 0))):
        cached_data = attr_cache.attribute_relations[attr_id]
        logger.info(f"DEBUG_API: 从缓存获取属性 {attr_id} 的关系数据: {cached_data}")
        return cached_data
    
    # 请求API获取数据
    logger.info(f"DEBUG_API: 请求API获取属性 {attr_id} 的关系数据")
    result = await plugin_instance._make_request(f"/api/attribute-relations/{attr_id}")
    if result and result.get("success"):
        data = result["data"]
        logger.info(f"DEBUG_API: API返回属性 {attr_id} 的关系数据: {data}")
        attr_cache.attribute_relations[attr_id] = data
        attr_cache.relations_timestamp[attr_id] = current_time
        return data
    else:
        logger.info(f"DEBUG_API: API请求失败或返回错误: {result}")
    
    return None

def format_attributes_list(attributes: List[Dict[str, Any]]) -> str:
    """格式化属性列表显示"""
    if not attributes:
        return "无法获取属性列表"
    
    message_lines = ["奥拉星属性系别列表:\n"]
    
    # 按ID排序
    sorted_attrs = sorted(attributes, key=lambda x: x["id"])
    
    for attr in sorted_attrs:
        message_lines.append(f"{attr['id']:2d}. {attr['name']}")
    
    message_lines.append(f"\n总计: {len(attributes)} 个属性系别")
    message_lines.append("使用 /ar_attr <属性ID> 查看该属性的克制关系")
    
    return "\n".join(message_lines)

def is_super_attribute(id: int) -> bool:
    """判断是否为超系属性"""
    return id > 22

def parse_relation(relation: str) -> float:
    """解析克制关系字符串为数值"""
    damage_mapping = {
        '': 1.0,     # 一般
        '1/2': 0.5,  # 微弱
        '-1': -1.0,  # 无效
        '2': 2.0,    # 克制
        '3': 3.0     # 绝对克制
    }
    
    if not relation or relation == '':
        return 1.0
    
    return damage_mapping.get(relation, 1.0)

def get_attribute_icon_url(id: int) -> str:
    """获取系别图标URL"""
    # 这里使用与前端相同的URL配置
    pet_attribute_prefix = "https://aola.rhapsody.toys/images/pet/attribute"
    
    # 特殊处理统一的原系和超系图标
    if id == 999:
        # 超系统一图标
        return f"{pet_attribute_prefix}/attribute999.png"
    if id == 1000:
        # 原系统一图标
        return f"{pet_attribute_prefix}/attribute1000.png"

    # 原有的系别图标逻辑
    if is_super_attribute(id):
        return f"{pet_attribute_prefix}/oldattribute{id}.png"
    return f"{pet_attribute_prefix}/attribute{id}.png"

async def download_image(url: str) -> Optional[bytes]:
    """下载图片"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.info(f"下载图片失败: {response.status} - {url}")
                    return None
    except Exception as e:
        logger.info(f"下载图片异常: {e}")
        return None

async def generate_attribute_image(attr_id: int, attr_name: str, relations: Dict[str, str],
                           all_attributes: List[Dict[str, Any]]) -> bytes:
    """生成属性克制关系图 - 三段式布局版本"""
    # 创建ID到名称的映射
    id_to_name = {attr["id"]: attr["name"] for attr in all_attributes}
    
    # 设置图片参数 - 适合三段式布局的尺寸
    width, height = 1200, 1600  # 调整为更适合三段式布局的尺寸
    
    # 现代化的配色方案
    background_color = (245, 247, 250)  # 浅蓝灰色背景
    text_color = (31, 41, 55)           # 深灰色文字
    title_color = (15, 23, 42)          # 深蓝灰色标题
    subtitle_color = (71, 85, 105)       # 中灰色副标题
    
    # 精致的克制关系配色
    colors = {
        'super': (239, 68, 68),      # 红色 - 绝对克制
        'strong': (251, 146, 60),    # 橙色 - 克制
        'weak': (34, 197, 94),       # 绿色 - 微弱
        'immune': (107, 114, 128),   # 灰色 - 无效
        'normal': (156, 163, 175),   # 浅灰色 - 一般
        'accent': (99, 102, 241)     # 紫蓝色 - 强调色
    }
    
    # 创建图片和绘图对象
    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)
    
    # 增强的圆角矩形绘制函数
    def draw_enhanced_rounded_rect(x, y, w, h, radius, fill, outline=None, outline_width=1, shadow=True):
        """增强的圆角矩形绘制，支持阴影和光泽效果"""
        # 绘制阴影
        if shadow:
            shadow_color = (0, 0, 0, 25)
            try:
                shadow_overlay = Image.new('RGBA', (w + 20, h + 20), (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow_overlay)
                shadow_draw.rounded_rectangle((8, 8, w + 12, h + 12), radius=radius, fill=shadow_color)
                image.paste(shadow_overlay, (x + 5, y + 5), shadow_overlay)
            except:
                pass
        
        # 绘制主矩形
        try:
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=outline, width=outline_width)
        except:
            draw.rectangle([x, y, x + w, y + h], fill=fill, outline=outline, width=outline_width)
        
        # 绘制高光效果
        if shadow:
            highlight_color = (255, 255, 255, 15)
            try:
                highlight_overlay = Image.new('RGBA', (w, h // 3), (0, 0, 0, 0))
                highlight_draw = ImageDraw.Draw(highlight_overlay)
                highlight_draw.rounded_rectangle((0, 0, w, h // 3), radius=radius, fill=highlight_color)
                image.paste(highlight_overlay, (x, y), highlight_overlay)
            except:
                pass
    
    def draw_circle_with_border(x, y, radius, fill, border_color, border_width=2):
        """绘制带边框的圆形"""
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                    outline=border_color, width=border_width)
    
    # 加载字体
    try:
        font_title = load_font_with_fallback(42)     # 标题字体
        font_large = load_font_with_fallback(32)     # 大号字体
        font_medium = load_font_with_fallback(26)    # 中号字体
        font_small = load_font_with_fallback(20)     # 小号字体
        font_tiny = load_font_with_fallback(16)      # 微小字体
    except Exception as e:
        logger.info(f"字体加载出现异常: {e}")
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()
    
    # 下载当前属性图标 - 放大图标尺寸
    current_icon = None
    try:
        async with aiohttp.ClientSession() as session:
            current_icon = await attr_cache.get_attribute_icon(session, attr_id)
            if current_icon:
                current_icon = current_icon.resize((70, 70))  # 从60x60放大到70x70
    except Exception as e:
        logger.info(f"下载当前属性图标失败: {e}")
    
    # ========== 顶部区域：当前属性显示 ==========
    top_panel_y = 30
    top_panel_height = 120  # 减少高度，因为不需要标题
    top_panel_width = width - 80
    top_panel_x = (width - top_panel_width) // 2
    
    # 绘制顶部面板背景
    draw_enhanced_rounded_rect(top_panel_x, top_panel_y, top_panel_width, top_panel_height,
                              20, (255, 255, 255), colors['accent'], 3)
    
    # 绘制当前属性信息 - 图标和文字居中显示
    if current_icon:
        # 计算图标位置：在面板中心偏左
        icon_x = top_panel_x + (top_panel_width - 70) // 2 - 60  # 70是图标宽度，向左偏移60像素
        icon_y = top_panel_y + (top_panel_height - 70) // 2  # 垂直居中
        image.paste(current_icon, (icon_x, icon_y), current_icon if 'A' in current_icon.getbands() else None)
    
    # 绘制当前属性名称 - 图标右侧，整体居中
    try:
        name_bbox = draw.textbbox((0, 0), attr_name, font=font_large)
        name_width = name_bbox[2] - name_bbox[0]
        name_height = name_bbox[3] - name_bbox[1]
    except:
        name_width = len(attr_name) * 18
        name_height = 26
    
    # 文字位置：图标右侧，整体居中对齐
    if current_icon:
        name_x = icon_x + 90  # 图标右侧间距
        name_y = icon_y + (70 - name_height) // 2  # 与图标垂直对齐
    else:
        # 如果没有图标，文字居中显示
        name_x = top_panel_x + (top_panel_width - name_width) // 2
        name_y = top_panel_y + (top_panel_height - name_height) // 2
    
    draw.text((name_x, name_y), attr_name, fill=title_color, font=font_large)
    
    # ========== 准备克制关系数据 ==========
    attack_relations = {
        'super': [],   # 攻击时3倍伤害
        'strong': [],  # 攻击时2倍伤害
        'weak': [],    # 攻击时1/2伤害
        'immune': []   # 攻击时无伤害
    }
    
    defend_relations = {
        'super': [],   # 被攻击时受到3倍伤害
        'strong': [],  # 被攻击时受到2倍伤害
        'weak': [],    # 被攻击时受到1/2伤害
        'immune': []   # 被攻击时免疫伤害
    }
    
    is_current_super = is_super_attribute(attr_id)
    
    # 处理攻击关系
    for target_id_str, multiplier in relations.items():
        target_id = int(target_id_str)
        target_name = id_to_name.get(target_id)
        
        if target_name is None:
            continue
            
        is_target_super = is_super_attribute(target_id)
        
        # 特殊处理：原系攻击超系
        if not is_current_super and is_target_super:
            if not any(icon_id == 999 for _, icon_id in attack_relations['weak']):
                attack_relations['weak'].append(("超系", 999))
            continue
            
        # 特殊处理：超系攻击原系
        if is_current_super and not is_target_super:
            if not any(icon_id == 1000 for _, icon_id in attack_relations['strong']):
                attack_relations['strong'].append(("原系", 1000))
            continue
            
        # 根据倍率分类
        damage_value = parse_relation(multiplier)
        if damage_value == 3.0:
            attack_relations['super'].append((target_name, target_id))
        elif damage_value == 2.0:
            attack_relations['strong'].append((target_name, target_id))
        elif damage_value == 0.5:
            attack_relations['weak'].append((target_name, target_id))
        elif damage_value == -1.0:
            attack_relations['immune'].append((target_name, target_id))
    
    # 处理防御关系
    for attr in all_attributes:
        other_attr_id = attr["id"]
        if other_attr_id == attr_id:
            continue
            
        other_attr_name = attr['name']
        other_relations = attr_cache.attribute_relations.get(other_attr_id, {})
        multiplier = other_relations.get(str(attr_id), "")
        
        is_other_super = is_super_attribute(other_attr_id)
        
        # 特殊处理：原系攻击超系
        if not is_other_super and is_current_super:
            if not any(icon_id == 1000 for _, icon_id in defend_relations['weak']):
                defend_relations['weak'].append(("原系", 1000))
            continue
            
        # 特殊处理：超系攻击原系
        if is_other_super and not is_current_super:
            if not any(icon_id == 999 for _, icon_id in defend_relations['strong']):
                defend_relations['strong'].append(("超系", 999))
            continue
            
        # 根据倍率分类
        damage_value = parse_relation(multiplier)
        if damage_value == 3.0:
            defend_relations['super'].append((other_attr_name, other_attr_id))
        elif damage_value == 2.0:
            defend_relations['strong'].append((other_attr_name, other_attr_id))
        elif damage_value == 0.5:
            defend_relations['weak'].append((other_attr_name, other_attr_id))
        elif damage_value == -1.0:
            defend_relations['immune'].append((other_attr_name, other_attr_id))
    
    # ========== 中间区域：攻击关系 ==========
    attack_panel_y = top_panel_y + top_panel_height + 40
    attack_panel_height = 480  # 稍微减少高度以适应新的布局
    attack_panel_width = width - 80
    attack_panel_x = (width - attack_panel_width) // 2
    
    # 绘制攻击关系面板背景
    draw_enhanced_rounded_rect(attack_panel_x, attack_panel_y, attack_panel_width, attack_panel_height,
                              15, (255, 255, 255), colors['strong'], 2)
    
    # 绘制攻击关系标题 - 修复PIL渲染问题
    attack_title = "攻击 攻击克制关系"
    try:
        attack_title_bbox = draw.textbbox((0, 0), attack_title, font=font_medium)
        attack_title_width = attack_title_bbox[2] - attack_title_bbox[0]
    except:
        attack_title_width = len(attack_title) * 20
    
    attack_title_x = attack_panel_x + 20
    attack_title_y = attack_panel_y + 15
    draw.text((attack_title_x, attack_title_y), attack_title, fill=colors['strong'], font=font_medium)
    
    # 绘制攻击关系内容
    await draw_relations_section(draw, image, attack_relations, attack_panel_x + 20, attack_title_y + 40,
                                attack_panel_width - 40, attack_panel_height - 60, colors, font_small, font_tiny)
    
    # ========== 底部区域：防御关系 ==========
    defend_panel_y = attack_panel_y + attack_panel_height + 40
    defend_panel_height = 480  # 稍微减少高度以适应新的布局
    defend_panel_width = width - 80
    defend_panel_x = (width - defend_panel_width) // 2
    
    # 绘制防御关系面板背景
    draw_enhanced_rounded_rect(defend_panel_x, defend_panel_y, defend_panel_width, defend_panel_height,
                              15, (255, 255, 255), colors['weak'], 2)
    
    # 绘制防御关系标题 - 修复PIL渲染问题
    defend_title = "防御 防御克制关系"
    try:
        defend_title_bbox = draw.textbbox((0, 0), defend_title, font=font_medium)
        defend_title_width = defend_title_bbox[2] - defend_title_bbox[0]
    except:
        defend_title_width = len(defend_title) * 20
    
    defend_title_x = defend_panel_x + 20
    defend_title_y = defend_panel_y + 15
    draw.text((defend_title_x, defend_title_y), defend_title, fill=colors['weak'], font=font_medium)
    
    # 绘制防御关系内容
    await draw_relations_section(draw, image, defend_relations, defend_panel_x + 20, defend_title_y + 40,
                                defend_panel_width - 40, defend_panel_height - 60, colors, font_small, font_tiny)
    
    # ========== 底部图例区域 ==========
    legend_y = defend_panel_y + defend_panel_height + 30
    legend_width = width - 100
    legend_height = 120
    legend_x = (width - legend_width) // 2
    
    # 边界检查：确保图例区域不会超出图片底部
    if legend_y + legend_height > height - 30:
        # 如果会超出，调整图例位置
        legend_y = height - legend_height - 30
    
    # 绘制图例面板背景
    draw_enhanced_rounded_rect(legend_x, legend_y, legend_width, legend_height,
                              12, (255, 255, 255), colors['accent'], 1)
    
    # 绘制图例标题
    draw.text((legend_x + 20, legend_y + 15), "克制关系说明", fill=title_color, font=font_medium)
    
    # 绘制图例项目 - 简化显示，删除emoji符号和前面的方块
    legend_items = [
        ("绝对克制", colors['super'], "3倍伤害"),
        ("克制", colors['strong'], "2倍伤害"),
        ("微弱", colors['weak'], "1/2伤害"),
        ("无效", colors['immune'], "无伤害")
    ]
    
    for i, (text, color, desc) in enumerate(legend_items):
        x_offset = legend_x + 20 + (i % 2) * (legend_width // 2 - 40)
        y_offset = legend_y + 45 + (i // 2) * 30
        
        # 绘制文字 - 直接显示关系类型和伤害倍率
        draw.text((x_offset + 10, y_offset), f"{text} {desc}", fill=color, font=font_small)
    
    # 保存图片到字节流
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr.getvalue()

async def draw_relations_section(draw, image, relations, x, y, width, height, colors, font_medium, font_small):
    """绘制克制关系区域的通用函数"""
    # 定义关系类型信息 - 简化显示，删除emoji符号
    relation_types = [
        ('super', '绝对克制', '3倍伤害'),
        ('strong', '克制', '2倍伤害'),
        ('weak', '微弱', '1/2伤害'),
        ('immune', '无效', '无伤害')
    ]
    
    current_y = y
    
    for rel_type, title, desc in relation_types:
        items = relations.get(rel_type, [])
        if not items:
            continue
        
        # 绘制关系类型标题
        try:
            title_bbox = draw.textbbox((0, 0), title, font=font_medium)
            title_width = title_bbox[2] - title_bbox[0]
        except:
            title_width = len(title) * 16
        
        # 绘制颜色指示器
        draw.rectangle([x, current_y, x + 15, current_y + 15], fill=colors[rel_type])
        
        # 绘制标题文字
        draw.text((x + 25, current_y), title, fill=colors[rel_type], font=font_medium)
        
        current_y += 25
        
        # 绘制属性图标和名称 - 水平排列，图标在左，文字在右
        items_per_row = 4  # 减少每行显示的数量以适应水平排列
        for i, (name, icon_id) in enumerate(items):
            row = i // items_per_row
            col = i % items_per_row
            
            item_x = x + col * 150
            item_y = current_y + row * 70
            
            # 获取并绘制图标 - 放大图标尺寸
            icon = None
            try:
                async with aiohttp.ClientSession() as session:
                    icon = await attr_cache.get_attribute_icon(session, icon_id)
                    if icon:
                        icon = icon.resize((60, 60))  # 从40x40放大到60x60
            except Exception as e:
                logger.info(f"获取属性图标失败: {e}")
            
            if icon:
                try:
                    image.paste(icon, (item_x, item_y), icon if 'A' in icon.getbands() else None)
                except:
                    image.paste(icon, (item_x, item_y))
            
            # 绘制属性名称 - 放在图标右侧
            try:
                name_bbox = draw.textbbox((0, 0), name, font=font_small)
                name_width = name_bbox[2] - name_bbox[0]
            except:
                name_width = len(name) * 8
            
            name_x = item_x + 70  # 图标右侧
            name_y = item_y + 20  # 垂直居中
            draw.text((name_x, name_y), name, fill=(31, 41, 55), font=font_small)
        
        # 计算该类型占用的行数
        rows_needed = (len(items) + items_per_row - 1) // items_per_row
        current_y += rows_needed * 70 + 20
        
        if current_y > y + height:
            break  # 防止超出区域边界

def format_attribute_relations(attr_id: int, attr_name: str, relations: Dict[str, str], 
                             all_attributes: List[Dict[str, Any]]) -> str:
    """格式化属性克制关系显示"""
    message_lines = [f"目标 {attr_name} 属性的克制关系:\n"]
    
    # 创建ID到名称的映射
    id_to_name = {attr["id"]: attr["name"] for attr in all_attributes}
    
    # 分类显示攻击方关系（当前属性攻击其他属性时的倍率）
    attack_strong = []      # 攻击时2倍伤害
    attack_super = []       # 攻击时3倍伤害
    attack_weak = []        # 攻击时1/2伤害
    attack_immune = []      # 攻击时无伤害
    attack_normal = []      # 攻击时正常伤害
    
    # 处理攻击关系 - 当前属性攻击其他属性时的倍率
    is_current_super = is_super_attribute(attr_id)
    
    # 调试日志：记录文本格式攻击分析开始
    logger.info(f"[DEBUG] 文本攻击分析开始 - 当前属性: {attr_name} (ID: {attr_id}, 超系: {is_current_super})")
    
    for target_id_str, multiplier in relations.items():
        target_id = int(target_id_str)
        target_name = id_to_name.get(target_id)
        
        # 跳过无效的属性ID
        if target_name is None:
            continue
            
        is_target_super = is_super_attribute(target_id)
        
        # 调试日志：记录每个属性的攻击关系分析
        logger.info(f"[DEBUG] 文本攻击分析 - 目标属性: {target_name} (ID: {target_id}, 超系: {is_target_super})")
        logger.info(f"[DEBUG] 文本攻击分析 - 倍率数据: {multiplier}")
        logger.info(f"[DEBUG] 文本攻击分析 - 条件判断: 原系攻击超系={not is_current_super and is_target_super}")
        logger.info(f"[DEBUG] 文本攻击分析 - 条件判断: 超系攻击原系={is_current_super and not is_target_super}")
        
        # 特殊处理：原系攻击超系固定为1/2倍伤害，统一显示为"超系"
        if not is_current_super and is_target_super:
            logger.info(f"[DEBUG] 文本攻击分析 - 触发特殊规则: 原系攻击超系，添加'超系'到attack_weak")
            # 检查是否已经添加了统一的超系图标（与React版本保持一致）
            if not any(item == "超系" for item in attack_weak):
                attack_weak.append("超系")
                logger.info(f"[DEBUG] 文本攻击分析 - 统一图标添加: 超系 -> attack_weak")
            else:
                logger.info(f"[DEBUG] 文本攻击分析 - 统一图标已存在，跳过添加: 超系")
            # 跳过后续的倍率处理，因为这是特殊规则
            continue
            
        # 特殊处理：超系攻击原系固定为2倍伤害，统一显示为"原系"
        if is_current_super and not is_target_super:
            logger.info(f"[DEBUG] 文本攻击分析 - 触发特殊规则: 超系攻击原系，添加'原系'到attack_strong")
            # 检查是否已经添加了统一的原系图标（与React版本保持一致）
            if not any(item == "原系" for item in attack_strong):
                attack_strong.append("原系")
                logger.info(f"[DEBUG] 文本攻击分析 - 统一图标添加: 原系 -> attack_strong")
            else:
                logger.info(f"[DEBUG] 文本攻击分析 - 统一图标已存在，跳过添加: 原系")
            # 跳过后续的倍率处理，因为这是特殊规则
            continue
            
        # 根据倍率分类
        damage_value = parse_relation(multiplier)
        logger.info(f"[DEBUG] 文本攻击分析 - 最终倍率分类: {damage_value}")
        
        if damage_value == 2.0:
            attack_strong.append(f"{target_name}")
            logger.info(f"[DEBUG] 文本攻击分析 - 最终分类: {damage_value} -> attack_strong (造成2倍伤害): {target_name}")
        elif damage_value == 3.0:
            attack_super.append(f"{target_name}")
            logger.info(f"[DEBUG] 文本攻击分析 - 最终分类: {damage_value} -> attack_super (造成3倍伤害): {target_name}")
        elif damage_value == 0.5:
            attack_weak.append(f"{target_name}")
            logger.info(f"[DEBUG] 文本攻击分析 - 最终分类: {damage_value} -> attack_weak (造成1/2伤害): {target_name}")
        elif damage_value == -1.0:
            attack_immune.append(f"{target_name}")
            logger.info(f"[DEBUG] 文本攻击分析 - 最终分类: {damage_value} -> attack_immune (无伤害): {target_name}")
        elif damage_value == 1.0:
            attack_normal.append(f"{target_name}")
            logger.info(f"[DEBUG] 文本攻击分析 - 最终分类: {damage_value} -> attack_normal (造成1倍伤害): {target_name}")
        else:
            logger.info(f"[DEBUG] 文本攻击分析 - 倍率 {damage_value} 未被分类到任何攻击类别")
    
    # 分类显示防御方关系（其他属性攻击当前属性时的倍率）
    defend_strong = []      # 被攻击时受到2倍伤害
    defend_super = []       # 被攻击时受到3倍伤害
    defend_weak = []        # 被攻击时受到1/2伤害
    defend_immune = []      # 被攻击时免疫伤害
    defend_normal = []      # 被攻击时受到正常伤害
    
    # 获取所有属性对当前属性的关系
    is_current_super = is_super_attribute(attr_id)
    
    # 调试日志：记录文本格式防御分析开始
    logger.info(f"[DEBUG] 文本防御分析开始 - 当前属性: {attr_name} (ID: {attr_id}, 超系: {is_current_super})")
    
    # 调试日志：检查缓存中的属性关系数据
    logger.info(f"[DEBUG] 文本防御分析 - 缓存中的属性关系数量: {len(attr_cache.attribute_relations)}")
    for cached_id, relations in attr_cache.attribute_relations.items():
        logger.info(f"[DEBUG] 文本防御分析 - 缓存的属性 {cached_id} 的关系: {relations}")
    
    for attr in all_attributes:
        other_attr_id = attr["id"]
        if other_attr_id == attr_id:
            continue
            
        other_attr_name = attr['name']
        # 获取其他属性对该属性的克制关系
        other_relations = attr_cache.attribute_relations.get(other_attr_id, {})
        multiplier = other_relations.get(str(attr_id), "")
        
        is_other_super = is_super_attribute(other_attr_id)
        
        # 调试日志：记录每个属性的防御关系分析
        logger.info(f"[DEBUG] 文本防御分析 - 其他属性: {other_attr_name} (ID: {other_attr_id}, 超系: {is_other_super})")
        logger.info(f"[DEBUG] 文本防御分析 - 倍率数据: {multiplier}")
        logger.info(f"[DEBUG] 文本防御分析 - 条件判断: 原系攻击超系={not is_other_super and is_current_super}")
        logger.info(f"[DEBUG] 文本防御分析 - 条件判断: 超系攻击原系={is_other_super and not is_current_super}")
        
        # 特殊处理：原系攻击超系固定为1/2倍伤害
        if not is_other_super and is_current_super:
            logger.info(f"[DEBUG] 文本防御分析 - 触发特殊规则: 原系攻击超系，添加'原系'到defend_weak")
            # 检查是否已经添加了统一的原系图标（使用ID去重，与React版本保持一致）
            if not any(item == "原系" for item in defend_weak):
                defend_weak.append("原系")
                logger.info(f"[DEBUG] 文本防御分析 - 统一图标添加: 原系 -> defend_weak")
            else:
                logger.info(f"[DEBUG] 文本防御分析 - 统一图标已存在，跳过添加: 原系")
            # 跳过后续的倍率处理，因为这是特殊规则

            continue
            
        # 特殊处理：超系攻击原系固定为2倍伤害
        if is_other_super and not is_current_super:
            logger.info(f"[DEBUG] 文本防御分析 - 触发特殊规则: 超系攻击原系，添加'超系'到defend_strong")
            # 检查是否已经添加了统一的超系图标（使用ID去重，与React版本保持一致）
            if not any(item == "超系" for item in defend_strong):
                defend_strong.append("超系")
                logger.info(f"[DEBUG] 文本防御分析 - 统一图标添加: 超系 -> defend_strong")
            else:
                logger.info(f"[DEBUG] 文本防御分析 - 统一图标已存在，跳过添加: 超系")
            # 跳过后续的倍率处理，因为这是特殊规则
            continue
            
        # 调试日志：检查是否到达超系vs超系的处理
        if is_other_super and is_current_super:
            logger.info(f"[DEBUG] 文本防御分析 - 超系vs超系情况: {other_attr_name}({other_attr_id}) 攻击 {attr_name}({attr_id})")
            logger.info(f"[DEBUG] 文本防御分析 - API倍率: '{multiplier}', 解析后倍率: {parse_relation(multiplier)}")
        
        # 根据倍率分类
        damage_value = parse_relation(multiplier)
        logger.info(f"[DEBUG] 文本防御分析 - 最终倍率分类: {damage_value}")
        
        if damage_value == 2.0:
            defend_strong.append(f"{attr['name']}")
            logger.info(f"[DEBUG] 文本防御分析 - 最终分类: {damage_value} -> defend_strong (受到2倍伤害): {attr['name']}")
        elif damage_value == 3.0:
            defend_super.append(f"{attr['name']}")
            logger.info(f"[DEBUG] 文本防御分析 - 最终分类: {damage_value} -> defend_super (受到3倍伤害): {attr['name']}")
        elif damage_value == 0.5:
            defend_weak.append(f"{attr['name']}")
            logger.info(f"[DEBUG] 文本防御分析 - 最终分类: {damage_value} -> defend_weak (受到1/2伤害): {attr['name']}")
        elif damage_value == -1.0:
            defend_immune.append(f"{attr['name']}")
            logger.info(f"[DEBUG] 文本防御分析 - 最终分类: {damage_value} -> defend_immune (免疫伤害): {attr['name']}")
        elif damage_value == 1.0:
            defend_normal.append(f"{attr['name']}")
            logger.info(f"[DEBUG] 文本防御分析 - 最终分类: {damage_value} -> defend_normal (受到1倍伤害): {attr['name']}")
        else:
            logger.info(f"[DEBUG] 文本防御分析 - 倍率 {damage_value} 未被分类到任何防御类别")
    
    # 攻击方克制关系
    message_lines.append("攻击方 (当前属性攻击其他属性时):")
    
    if attack_super:
        message_lines.append("  爆炸 绝对克制 (3倍伤害):")
        for name in attack_super:
            message_lines.append(f"     • {name}")
    
    if attack_strong:
        message_lines.append("  火焰 克制 (2倍伤害):")
        for name in attack_strong:
            message_lines.append(f"     • {name}")
    
    if attack_weak:
        message_lines.append("  雪花 微弱 (1/2伤害):")
        for name in attack_weak:
            message_lines.append(f"     • {name}")
    
    if attack_immune:
        message_lines.append("  盾牌 无效 (无伤害):")
        for name in attack_immune:
            message_lines.append(f"     • {name}")
    
    if attack_normal:
        message_lines.append("  箭头 一般 (1倍伤害):")
        # 只显示前10个，避免信息过载
        for name in attack_normal[:10]:
            message_lines.append(f"     • {name}")
        if len(attack_normal) > 10:
            message_lines.append(f"     ... 还有 {len(attack_normal) - 10} 个")
    
    if not (attack_super or attack_strong or attack_weak or attack_immune or attack_normal):
        message_lines.append("  箭头 对所有属性造成正常伤害(1倍)")
    
    message_lines.append("")
    
    # 防御方克制关系
    message_lines.append("防御方 (其他属性攻击当前属性时):")
    
    if defend_super:
        message_lines.append("  爆炸 绝对克制 (受到3倍伤害):")
        for name in defend_super:
            message_lines.append(f"     • {name}")
    
    if defend_strong:
        message_lines.append("  火焰 克制 (受到2倍伤害):")
        for name in defend_strong:
            message_lines.append(f"     • {name}")
    
    if defend_weak:
        message_lines.append("  雪花 微弱 (受到1/2伤害):")
        for name in defend_weak:
            message_lines.append(f"     • {name}")
    
    if defend_immune:
        message_lines.append("  盾牌 无效 (免疫伤害):")
        for name in defend_immune:
            message_lines.append(f"     • {name}")
    
    if defend_normal:
        message_lines.append("  箭头 一般 (受到1倍伤害):")
        # 只显示前10个，避免信息过载
        for name in defend_normal[:10]:
            message_lines.append(f"     • {name}")
        if len(defend_normal) > 10:
            message_lines.append(f"     ... 还有 {len(defend_normal) - 10} 个")
    
    if not (defend_super or defend_strong or defend_weak or defend_immune or defend_normal):
        message_lines.append("  箭头 来自所有属性的攻击都受到正常伤害(1倍)")
    
    message_lines.append("")
    message_lines.append("说明:")
    message_lines.append("   • 3 = 绝对克制 (3倍伤害)")
    message_lines.append("   • 2 = 克制 (2倍伤害)")
    message_lines.append("   • 1/2 = 微弱 (1/2伤害)")
    message_lines.append("   • -1 = 无效 (无伤害)")
    message_lines.append("   • 空 = 一般 (1倍伤害)")
    message_lines.append("\n使用 /ar_attr_image <属性ID> 可以获取图片版的克制关系图")
    
    return "\n".join(message_lines)
