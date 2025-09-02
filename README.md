# AstrBot 奥拉星封包查询插件

[![文档](https://img.shields.io/badge/AstrBot-%E6%96%87%E6%A1%A3-blue)](https://astrbot.app)
[![aiohttp](https://img.shields.io/pypi/v/aiohttp.svg)](https://pypi.org/project/aiohttp/)
[![后端项目](https://img.shields.io/badge/Backend-Aolarhapsody-green)](https://github.com/vmoranv/aolarhapsody)

这是一个为 [AstrBot](https://astrbot.app) 开发的奥拉星封包查询插件，通过 [Aolarhapsody](https://github.com/vmoranv/aolarhapsody) 后端 API 获取奥拉星游戏封包信息。

## ✨ 核心特性

- 📦 **封包查询**: 获取奥拉星游戏现有封包列表
- 🔍 **智能搜索**: 支持正则表达式模糊搜索封包
- 📄 **分页浏览**: 支持分页查看大量封包数据
- ⚙️ **简单配置**: 只需配置后端 API 地址即可使用
- 🔐 **安全管理**: 通过 WebUI 安全管理 API 配置
- 🔮 **属性查询**: 支持查询奥拉星属性系别及克制关系
- 🖼️ **图像展示**: 支持生成属性克制关系图

## 🎯 主要功能

### 封包查询
- `/ar_existingpacket` - 获取现有封包列表（默认显示前20个）
- `/ar_existingpacket next` - 显示下20个封包
- `/ar_existingpacket prev` - 显示上20个封包
- `/ar_existingpacket <名称>` - 搜索匹配名称的封包（支持正则表达式）

### 加解密功能
- `/ar_decrypt <Base64内容>` - 将Base64内容解密为JSON格式
- `/ar_encrypt <JSON内容>` - 将JSON内容加密为Base64格式

### 属性查询
- `/ar_attr ls` - 列出所有属性系别
- `/ar_attr <属性ID>` - 查看特定属性的克制关系（按攻击方和防御方分别显示）
- `/ar_attr_image <属性ID>` - 生成特定属性的克制关系图

### 帮助信息
- `/ar_help` - 显示帮助信息

## 🚀 快速开始

### 前置条件

- Python >= 3.10
- 已部署的 AstrBot 实例 (v3.x+)
- 可访问的 [Aolarhapsody](https://github.com/vmoranv/aolarhapsody) 后端服务

### 安装步骤

1. **克隆插件到 AstrBot 插件目录**
   ```bash
   cd /path/to/astrbot/data/plugins
   git clone https://github.com/vmoranv/astrbot_plugin_aolastar.git
   ```

2. **确认依赖文件**
   ```txt
   # requirements.txt
   aiohttp>=3.8.0
   Pillow>=8.0.0
   ```

3. **重启 AstrBot** 以加载插件和依赖

### 配置插件

1. 打开 AstrBot WebUI
2. 进入 `插件管理` -> 找到奥拉星插件
3. 点击 `插件配置`，填写以下信息：
   - **API 基础地址**: 必填，Aolarhapsody 后端服务地址

4. 保存配置

### 后端服务部署

你需要先部署 [Aolarhapsody](https://github.com/vmoranv/aolarhapsody) 后端服务，或使用现有的服务地址。

后端服务提供以下 API 接口：
- `GET /api/existing-activities` - 获取现有封包列表
- `GET /api/skill-attributes` - 获取属性列表
- `GET /api/attribute-relations/{id}` - 获取特定属性的克制列表

详细的后端部署说明请参考：[Aolarhapsody 项目文档](https://github.com/vmoranv/aolarhapsody)

## 📝 使用示例

```bash
# 获取帮助信息
/ar_help

# 获取封包列表（默认前20个）
/ar_existingpacket

# 翻页查看
/ar_existingpacket next    # 下一页
/ar_existingpacket prev    # 上一页

# 搜索封包
/ar_existingpacket 石矶娘娘     # 搜索包含"石矶娘娘"的封包
/ar_existingpacket .*挑战.*    # 使用正则表达式搜索包含"挑战"的封包
/ar_existingpacket 哪吒        # 搜索包含"哪吒"的封包

# 属性查询
/ar_attr ls               # 列出所有属性系别
/ar_attr 9                # 查看火属性的克制关系（按攻击方和防御方分别显示）
/ar_attr 10               # 查看水属性的克制关系（按攻击方和防御方分别显示）
/ar_attr_image 50         # 生成超上古·逆属性的克制关系图

# 属性克制关系示例输出:
# 🎯 超上古·逆 属性的克制关系:
#
# ⚔️ 攻击方 (当前属性攻击其他属性时):
#   🔥 2倍伤害:
#      • 普通
#      • 格斗
#      • 飞行
#      ...
#
# 🛡 防御方 (其他属性攻击当前属性时):
#   🔥 受到2倍伤害:
#      • 超王
#      • 仙灵
#      • 虚境
#   ...
```

## ⚙️ 配置选项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_base_url` | Aolarhapsody 后端服务地址 | 必填 |

### 配置说明

- **api_base_url**: Aolarhapsody 后端服务的地址，插件会自动添加 `http://` 协议前缀（如果未指定协议）
- 插件会调用 `{api_base_url}/api/existing-activities` 接口获取封包数据
- 插件会调用 `{api_base_url}/api/skill-attributes` 接口获取属性列表
- 插件会调用 `{api_base_url}/api/attribute-relations/{id}` 接口获取属性克制关系

## 🛠️ 开发构建

```bash
# 克隆项目
git clone https://github.com/vmoranv/astrbot_plugin_aolastar.git
cd astrbot_plugin_aolastar

# 安装依赖
pip install -r requirements.txt

# 部署到 AstrBot
cp -r . /path/to/astrbot/data/plugins/astrbot_plugin_aolastar/
```

## 🔧 故障排除

### 常见问题

**API 基础地址未配置**
- 检查插件配置中是否正确填写了 `api_base_url`

**连接错误**
- 检查 API 基础地址是否正确且可访问
- 确认 Aolarhapsody 后端服务正在运行
- 检查网络连接和防火墙设置

**获取封包列表失败**
- 确认后端服务的 `/api/existing-activities` 接口正常工作
- 检查后端服务日志是否有错误信息

**获取属性信息失败**
- 确认后端服务的 `/api/skill-attributes` 和 `/api/attribute-relations/{id}` 接口正常工作
- 检查后端服务日志是否有错误信息

**模块未找到**
- 重启 AstrBot 以确保依赖正确安装
- 检查 `requirements.txt` 中的依赖是否已安装

**图片生成功能不可用**
- 确保已安装 Pillow 库
- 目前图片生成功能仅支持 OneBot 平台

**图片中文字体显示异常**
- 插件使用系统默认字体生成图片，不同系统显示效果可能有所差异
- 如果对字体显示效果有特殊要求，建议在系统层面安装合适的中文字体

## 📖 更多信息

- [AstrBot 官方文档](https://astrbot.app/)
- [插件开发指南](https://astrbot.app/develop/plugin.html)
- [Aolarhapsody 后端项目](https://github.com/vmoranv/aolarhapsody)
- [问题反馈](https://github.com/vmoranv/astrbot_plugin_aolastar/issues)

## ⭐ 项目统计

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=vmoranv/astrbot_plugin_aolastar&type=Date)](https://star-history.com/#vmoranv/astrbot_plugin_aolastar&Date)

</div>

## 📄 许可证

本项目遵循开源许可证，具体许可证信息请查看项目根目录下的 LICENSE 文件。

---

## 🔗 相关项目

- **前端插件**: [astrbot_plugin_aolastar](https://github.com/vmoranv/astrbot_plugin_aolastar) - 本项目
- **后端服务**: [Aolarhapsody](https://github.com/vmoranv/aolarhapsody) - 提供封包数据的后端 API 服务

## 📋 功能特点

- **轻量级**: 插件体积小，依赖少，启动快
- **易配置**: 只需配置一个 API 地址即可使用
- **分页支持**: 自动分页显示大量数据，避免消息过长
- **搜索功能**: 支持正则表达式搜索，查找特定封包
- **缓存机制**: 智能缓存 API 数据，减少重复请求
- **属性查询**: 支持查询奥拉星属性克制关系，帮助战斗策略制定
- **图像展示**: 可生成属性克制关系图，更直观地展示信息

---

**注意**: 使用本插件需遵守奥拉星游戏服务条款和相关法律法规。请合理使用 API 避免频繁请求。