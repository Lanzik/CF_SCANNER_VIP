import subprocess
import time
from curl_cffi.requests import Session
import os

def test_with_impersonation(target_url, proxy_address):
    """
    با جعل هویت مرورگر کروم، اتصال و پینگ را تست می‌کند.
    """
    proxies = {"http": proxy_address, "https": proxy_address}
    session = Session(proxies=proxies, impersonate="chrome110")
    
    print(f"▶️ Testing connection to {target_url}...")
    
    try:
        response = session.get(target_url, timeout=20)

        if 200 <= response.status_code < 300:
            print(f"✅ Connection successful! (Status: {response.status_code})")
            ping_ms = response.elapsed * 1000
            print(f"⏱️ Round-trip latency: {ping_ms:.0f} ms")
        else:
            print(f"❌ Connection failed with status code: {response.status_code}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    xray_process = None
    config_file = "config.json"
    xray_executable = "./xray"  # <-- مسیر فایل اجرایی در همین پوشه
    local_proxy = "socks5h://127.0.0.1:10808"

    if not os.path.exists(config_file):
        print(f"🚨 Error: Config file '{config_file}' not found!")
        exit()
    
    if not os.path.exists(xray_executable):
        print(f"🚨 Error: Xray executable '{xray_executable}' not found in the current directory!")
        exit()

    try:
        print("🚀 Starting Xray core from the current directory...")
        command = [xray_executable, "run", "-c", config_file]
        xray_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        print("⏳ Waiting for Xray to initialize...")
        time.sleep(5)

        if xray_process.poll() is not None:
            print("‼️ Xray core failed to start. Reading error logs:")
            error_output = xray_process.stderr.read()
            print(error_output)
            exit()
        
        print("\n✅ Xray is running. Starting tests...\n" + "="*30)

        sites_to_test = [
            "https://www.google.com",
            "https://www.youtube.com",
            "https://www.x.com"
        ]

        for site in sites_to_test:
            test_with_impersonation(site, local_proxy)
            print("-" * 30)

    except Exception as e:
        print(f"An unexpected error occurred in the main script: {e}")
    finally:
        if xray_process and xray_process.poll() is None:
            print("\n🛑 Stopping Xray core...")
            xray_process.terminate()
            xray_process.wait()
            print("✅ Xray core stopped.")