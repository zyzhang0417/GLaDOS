import requests
import datetime
import random
import os
import time
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
        "Mozilla/5.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    ]
    return {
        "Content-Type": "application/json",
        "Cookie": cookie,
        "User-Agent": random.choice(user_agents)
    }

def format_days(days_str):
    days = float(days_str)
    if days.is_integer():
        return str(int(days))
    return f"{days:.8f}".rstrip('0').rstrip('.')

def send_notification(sign_messages, status_messages, bot_token, chat_id):
    if not bot_token or not chat_id:
        print("Telegram 配置不完整，跳过通知")
        return
    
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
        print("Telegram 通知发送成功")
    except requests.RequestException as e:
        print(f"发送 Telegram 消息失败: {e}")

def check_account_status(email, cookie, proxy):
    url = "https://glados.cloud/api/user/status"
    headers = generate_headers(cookie)
    try:
        # 如果代理配置为空，则不使用代理
        if proxy and proxy.get("http"):
            response = requests.get(url, headers=headers, proxies=proxy, timeout=10)
        else:
            response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status API 响应码: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        left_days = format_days(data['data']['leftDays'])
        return f"<b>{email}</b>: 剩余 {left_days} 天 🗓️"
    except requests.RequestException as e:
        return f"<b>{email}</b>: 获取状态失败 - {str(e)} ❌"
    except (KeyError, ValueError) as e:
        print(f"Status API 原始响应: {response.text[:200]}")
        return f"<b>{email}</b>: 解析响应失败 - {str(e)} ❌"

def sign(email, cookie, proxy):
    url = "https://glados.cloud/api/user/checkin"
    headers = generate_headers(cookie)
    data = {"token": "glados.cloud"}
    
    try:
        # 如果代理配置为空，则不使用代理
        if proxy and proxy.get("http"):
            response = requests.post(url, headers=headers, json=data, proxies=proxy, timeout=10)
        else:
            response = requests.post(url, headers=headers, json=data, timeout=10)
        
        print(f"Checkin API 响应码: {response.status_code}")
        print(f"Checkin API 原始响应: {response.text[:500]}")
        
        response.raise_for_status()
        
        # 尝试解析 JSON
        try:
            response_data = response.json()
            raw_message = response_data.get("message", "")
            translated_message = translate_message(raw_message)
        except ValueError as e:
            print(f"JSON 解析失败，原始响应: {response.text}")
            translated_message = f"解析响应失败 ❌"
            
    except requests.RequestException as e:
        print(f"请求异常: {str(e)}")
        translated_message = f"请求失败: {e} ❌"
    
    beijing_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    log_message = f"{beijing_time.strftime('%Y-%m-%d %H:%M')} {email}: {translated_message}"
    print(log_message)
    return f"<b>{email}</b>: {translated_message}"

def multi_account_sign():
    load_dotenv()
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    
    # 处理代理配置
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    proxy = None
    if http_proxy or https_proxy:
        proxy = {
            "http": http_proxy,
            "https": https_proxy
        }
        print(f"使用代理: {proxy}")
    else:
        print("未配置代理")

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
        print("未找到账号信息，请检查环境变量")
        return

    print(f"\n开始处理 {len(accounts)} 个账号...\n")
    
    sign_messages = []
    status_messages = []
    for idx, (email, cookie) in enumerate(accounts, 1):
        print(f"--- 处理账号 {idx}/{len(accounts)}: {email} ---")
        sign_result = sign(email, cookie, proxy)
        sign_messages.append(sign_result)
        
        time.sleep(2)  # 签到后等待2秒再查询状态
        
        status_result = check_account_status(email, cookie, proxy)
        status_messages.append(status_result)
        
        if idx < len(accounts):
            wait_time = random.randint(5, 15)
            print(f"等待 {wait_time} 秒后处理下一个账号...\n")
            time.sleep(wait_time)

    print("\n所有账号处理完成，准备发送通知...")
    send_notification(sign_messages, status_messages, bot_token, chat_id)

if __name__ == "__main__":
    multi_account_sign()
