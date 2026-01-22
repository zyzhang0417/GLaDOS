import requests
import datetime
import random
import os
import time
import json
from dotenv import load_dotenv

def translate_message(raw_message):
    if raw_message == "Please Try Tomorrow":
        return "签到失败，请明天再试 🤖"
    elif "Checkin! Got" in raw_message:
        points = raw_message.split("Got ")[1].split(" Points")[0]
        return f"签到成功，获得{points}积分 🎉"
    elif raw_message == "Checkin Repeats! Please Try Tomorrow":
        return "重复签到，请明天再试 🔁"
    else:
        return f"未知的签到结果: {raw_message} ❓"

def generate_headers(cookie):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 10; zh-CN; SM-G9750) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.1 Safari/605.1.15",
    ]
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json;charset=UTF-8",
        "Cookie": cookie,
        "Origin": "https://glados.cloud",
        "Referer": "https://glados.cloud/console/checkin",
        "User-Agent": random.choice(user_agents)
    }

def format_days(days_str):
    days = float(days_str)
    if days.is_integer():
        return str(int(days))
    return f"{days:.8f}".rstrip('0').rstrip('.')

def send_notification(sign_messages, status_messages, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    sign_text = "🔔 GLaDOS 签到结果:\n" + "\n".join(sign_messages)
    status_text = "\n⏳ GLaDOS 账号状态:\n" + "\n".join(status_messages)
    beijing_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    current_time = beijing_time.strftime("%Y-%m-%d %H:%M")
    text = f"🕒 当前时间: {current_time}\n\n{sign_text}\n{status_text}\n\n✅ 签到任务完成"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"发送 Telegram 消息失败: {e}")

def check_account_status(email, cookie, proxy):
    url = "https://glados.cloud/api/user/status"
    headers = generate_headers(cookie)
    try:
        print(f"检查状态 - {email}: 发送请求到 {url}")
        print(f"Cookie 前10位: {cookie[:10]}...")
        
        response = requests.get(url, headers=headers, proxies=proxy if proxy else None, timeout=15)
        print(f"状态响应状态码: {response.status_code}")
        print(f"状态响应内容前200字符: {response.text[:200]}")
        
        response.raise_for_status()
        data = response.json()
        left_days = format_days(data['data']['leftDays'])
        return f"<b>{email}</b>: 剩余 {left_days} 天 🗓️"
    except requests.RequestException as e:
        return f"<b>{email}</b>: 获取状态失败 - {str(e)} ❌"
    except (KeyError, ValueError) as e:
        return f"<b>{email}</b>: 解析响应失败 - {str(e)} | 响应: {response.text[:100]} ❌"

def sign(email, cookie, proxy):
    url = "https://glados.cloud/api/user/checkin"
    headers = generate_headers(cookie)
    data = {"token": "glados.cloud"}
    
    try:
        print(f"签到 - {email}: 发送请求到 {url}")
        print(f"请求数据: {data}")
        print(f"Cookie 前10位: {cookie[:10]}...")
        
        response = requests.post(url, headers=headers, json=data, proxies=proxy if proxy else None, timeout=15)
        print(f"签到响应状态码: {response.status_code}")
        print(f"签到响应内容前200字符: {response.text[:200]}")
        
        response.raise_for_status()
        
        # 尝试解析 JSON
        try:
            response_data = response.json()
            raw_message = response_data.get("message", "")
            translated_message = translate_message(raw_message)
        except json.JSONDecodeError:
            # 如果不是 JSON，检查是否是 HTML 页面
            if "<html" in response.text.lower():
                translated_message = "响应是HTML页面，可能是Cookie过期或需要登录"
            else:
                translated_message = f"响应不是有效的JSON: {response.text[:100]}"
                
    except requests.RequestException as e:
        translated_message = f"请求失败: {str(e)}"
    except ValueError:
        translated_message = f"解析响应失败: {response.text[:100] if 'response' in locals() else '无响应'}"

    beijing_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    log_message = f"{beijing_time.strftime('%Y-%m-%d %H:%M')} {email}: {translated_message}"
    print(log_message)
    return f"<b>{email}</b>: {translated_message}"

def multi_account_sign():
    load_dotenv()
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    
    # 获取代理配置（可选）
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    proxy = None
    if http_proxy and https_proxy:
        proxy = {
            "http": http_proxy,
            "https": https_proxy
        }
        print(f"使用代理: {proxy}")
    else:
        print("未配置代理，直接连接")

    accounts = []
    i = 1
    while True:
        email = os.getenv(f"GLADOS_EMAIL_{i}")
        cookie = os.getenv(f"GLADOS_COOKIE_{i}")
        if not email or not cookie:
            break
        accounts.append((email, cookie))
        print(f"找到账号 {i}: {email}")
        i += 1

    if not accounts:
        print("未找到账号信息，请检查 .env 文件")
        return

    sign_messages = []
    status_messages = []
    for email, cookie in accounts:
        print(f"\n{'='*50}")
        print(f"处理账号: {email}")
        sign_result = sign(email, cookie, proxy)
        sign_messages.append(sign_result)
        status_result = check_account_status(email, cookie, proxy)
        status_messages.append(status_result)
        time.sleep(random.randint(5, 15))

    send_notification(sign_messages, status_messages, bot_token, chat_id)

if __name__ == "__main__":
    multi_account_sign()
