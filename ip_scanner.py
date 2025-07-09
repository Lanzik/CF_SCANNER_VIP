import subprocess
import time
import json
import os
import ipaddress
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- Configuration Settings ---
BASE_CONFIG_FILE = "config.json"
XRAY_EXECUTABLE = "./xray"
TEST_URL = "https://www.google.com" # A reliable site for testing
RESULTS_FILE = "working_ips.txt"
MAX_WORKERS = 8
START_PORT = 9001

# --- Core Functions ---

def run_ping_test(proxy_address, target_url):
    """Tests the ping by impersonating a browser and returns the result."""
    try:
        session = Session(proxies={"http": proxy_address, "https": proxy_address}, impersonate="chrome110")
        response = session.get(target_url, timeout=10)
        if 200 <= response.status_code < 300:
            return response.elapsed * 1000  # Return ping in milliseconds
    except Exception:
        return None
    return None

def test_ip_address(ip_port_tuple):
    """Takes an (IP, local_port) tuple, updates config, runs Xray, and performs a test."""
    ip, local_port = ip_port_tuple
    temp_config_file = f"temp_config_{local_port}.json"
    local_proxy = f"socks5h://127.0.0.1:{local_port}"
    xray_process = None
    
    try:
        with open(BASE_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        config["outbounds"][0]["settings"]["vnext"][0]["address"] = str(ip)
        config["inbounds"][0]["port"] = local_port

        with open(temp_config_file, 'w') as f:
            json.dump(config, f)

        command = [XRAY_EXECUTABLE, "run", "-c", temp_config_file]
        xray_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)

        if xray_process.poll() is not None:
            return None, ip

        ping_result = run_ping_test(local_proxy, TEST_URL)
        return ping_result, ip

    finally:
        if xray_process and xray_process.poll() is None:
            xray_process.terminate()
            xray_process.wait()
        if os.path.exists(temp_config_file):
            os.remove(temp_config_file)

# --- IP Sourcing Functions ---

def get_ips_from_cidr():
    """Prompts user for a CIDR range and returns a list of IPs."""
    while True:
        try:
            cidr_range = input("لطفا رنج IP را در فرمت CIDR وارد کنید (مثال: 1.1.1.0/24): ")
            ip_network = ipaddress.ip_network(cidr_range, strict=False)
            print(f"استخراج {ip_network.num_addresses} آدرس IP...")
            return [str(ip) for ip in ip_network.hosts()]
        except ValueError:
            print("🚨 خطا: فرمت CIDR نامعتبر است. لطفاً دوباره تلاش کنید.")

def get_ips_from_file():
    """Prompts user for a file path and returns a list of IPs from it."""
    while True:
        file_path = input("لطفا مسیر فایل نتایج را وارد کنید: ")
        if not os.path.exists(file_path):
            print(f"🚨 خطا: فایل '{file_path}' پیدا نشد. لطفاً مسیر را بررسی کرده و دوباره تلاش کنید.")
            continue
        
        ips = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Extracts IP from lines like "IP: 1.2.3.4, Ping: 123 ms"
                    match = re.search(r"IP:\s*([\d\.]+)", line)
                    if match:
                        ips.append(match.group(1))
            if not ips:
                print(f"⚠️ هشدار: هیچ آدرس IP معتبری در فایل '{file_path}' پیدا نشد.")
            return ips
        except Exception as e:
            print(f"🚨 خطا در خواندن فایل: {e}")
            return []

# --- Main Scanner Logic ---

def run_scanner(ips_to_test):
    """Takes a list of IPs and runs the parallel scanner."""
    if not ips_to_test:
        print("😔 هیچ آدرس IP برای اسکن وجود ندارد. خروج.")
        return

    print(f"🔬 Starting parallel IP scan for {len(ips_to_test)} addresses with {MAX_WORKERS} workers.")
    
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)

    working_ips = []
    ports_for_test = range(START_PORT, START_PORT + len(ips_to_test))
    tasks = zip(ips_to_test, ports_for_test)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ip = {executor.submit(test_ip_address, task): task[0] for task in tasks}

        for future in tqdm(as_completed(future_to_ip), total=len(future_to_ip), desc="Scanning IPs"):
            ip = future_to_ip[future]
            try:
                ping, _ = future.result()
                if ping is not None:
                    ping_ms = int(ping)
                    tqdm.write(f"✅ SUCCESS! IP: {ip:<15} | Ping: {ping_ms} ms")
                    result_line = f"IP: {ip}, Ping: {ping_ms} ms\n"
                    with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
                        f.write(result_line)
                    working_ips.append({"ip": ip, "ping": ping_ms})
                else:
                    tqdm.write(f"❌ FAILED!  IP: {ip}")
            except Exception as exc:
                tqdm.write(f" A task for IP {ip} generated an exception: {exc}")

    print("\n" + "="*30)
    print("Scanner finished.")

    if working_ips:
        sorted_ips = sorted(working_ips, key=lambda x: x["ping"])
        print(f"\n🏆 Top 5 Working IPs (saved in '{RESULTS_FILE}'):")
        for item in sorted_ips[:5]:
            print(f"  - IP: {item['ip']:<15} | Ping: {item['ping']} ms")
    else:
        print("😔 No working IPs found in this range.")

# --- Main Execution ---

if __name__ == "__main__":
    ips_to_scan = []
    
    while True:
        print("\nلطفا روش اسکن را انتخاب کنید:")
        print("1. اسکن از طریق رنج IP (CIDR)")
        print("2. اسکن از طریق فایل نتایج")
        choice = input("انتخاب شما (1 یا 2): ")

        if choice == '1':
            ips_to_scan = get_ips_from_cidr()
            break
        elif choice == '2':
            ips_to_scan = get_ips_from_file()
            break
        else:
            print("🚨 خطا: انتخاب نامعتبر است. لطفاً 1 یا 2 را وارد کنید.")

    # Run the scanner with the collected IPs
    run_scanner(ips_to_scan)