import json
import base64

def decrypt_base64_to_json(content):
    """将Base64内容解密为JSON格式"""
    try:
        # 解码Base64
        decoded_bytes = base64.b64decode(content)
        decoded_str = decoded_bytes.decode('utf-8')
        
        # 将字符串解析为JSON对象
        json_data = json.loads(decoded_str)
        
        # 返回格式化后的JSON字符串
        return json.dumps(json_data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"解密错误: {str(e)}"

def encrypt_json_to_base64(content):
    """将JSON内容加密为Base64格式"""
    try:
        # 尝试加载JSON
        json_data = json.loads(content)
        
        # 转换为紧凑JSON格式
        compact_json = json.dumps(json_data, separators=(',', ':'), ensure_ascii=False)
        
        # 编码为Base64
        encoded_bytes = base64.b64encode(compact_json.encode('utf-8'))
        return encoded_bytes.decode('utf-8')
    except Exception as e:
        return f"加密错误: {str(e)}"

def detect_file_content(content):
    """检测文件内容类型"""
    # 尝试解析为JSON
    try:
        json.loads(content)
        return 'json'
    except:
        pass
    
    # 检查是否是有效的Base64
    try:
        base64.b64decode(content)
        return 'base64'
    except:
        pass
    
    return 'unknown'

def process_decrypt(content):
    """处理解密操作的辅助函数"""
    file_type = detect_file_content(content)
    if file_type == 'base64':
        return decrypt_base64_to_json(content)
    else:
        return "错误：内容不是有效的Base64格式"

def process_encrypt(content):
    """处理加密操作的辅助函数"""
    file_type = detect_file_content(content)
    if file_type == 'json':
        return encrypt_json_to_base64(content)
    else:
        return "错误：内容不是有效的JSON格式"
