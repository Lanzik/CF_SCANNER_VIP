import subprocess
import time
import json
import os
import ipaddress
from curl_cffi.requests import Session

# --- Configuration Settings ---
BASE_CONFIG_FILE = "config.json"
TEMP_CONFIG_FILE = "temp_config.json"
XRAY_EXECUTABLE = "./xray"
LOCAL_PROXY = "socks5h://127.0.0.1:10808"
CIDR_RANGE = "173.245.48.0/20"  # <-- Enter the desired IP range here
TEST_URL = "https://www.youtube.com"
RESULTS_FILE = "working_ips.txt"  # <-- Filename for saving results

def run_ping_test(proxy_address, target_url):
    """Tests the ping by impersonating a browser and returns the result."""
    try:
        session = Session(proxies={"http": proxy_address, "https": proxy_address}, impersonate="chrome110")
        response = session.get(target_url, timeout=10)
        if 200 <= response.status_code < 300:
            return response.elapsed * 1000  # Return ping in milliseconds
    except Exception:
        return None # On any error, return None
    return None

def test_ip_address(ip):
    """Takes an IP, updates the config, runs Xray, and performs a test."""
    xray_process = None
    try:
        # 1. Read and update the config
        with open(BASE_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Access the address field and modify it
        config["outbounds"][0]["settings"]["vnext"][0]["address"] = str(ip)

        with open(TEMP_CONFIG_FILE, 'w') as f:
            json.dump(config, f)

        # 2. Run the Xray core with the temporary config
        command = [XRAY_EXECUTABLE, "run", "-c", TEMP_CONFIG_FILE]
        xray_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4) # Time for Xray to initialize

        # If Xray closes immediately, this IP doesn't work
        if xray_process.poll() is not None:
            return None

        # 3. Run the ping test
        ping_result = run_ping_test(LOCAL_PROXY, TEST_URL)
        return ping_result

    except (KeyError, IndexError):
        print("🚨 Error: Could not find the 'address' field in the config.json. Check the structure.")
        return "CONFIG_ERROR"
    finally:
        # 4. Stop Xray and delete the temporary file
        if xray_process and xray_process.poll() is None:
            xray_process.terminate()
            xray_process.wait()
        if os.path.exists(TEMP_CONFIG_FILE):
            os.remove(TEMP_CONFIG_FILE)

if __name__ == "__main__":
    print(f"🔬 Starting IP scan for range: {CIDR_RANGE}")
    
    # If the results file already exists, delete it
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)
    
    try:
        ip_network = ipaddress.ip_network(CIDR_RANGE)
    except ValueError:
        print("🚨 Error: Invalid CIDR range format.")
        exit()

    working_ips = []

    for ip in ip_network.hosts():
        print(f"[*] Testing IP: {ip}", end="", flush=True)
        result = test_ip_address(str(ip))
        
        # If the config structure is wrong, stop the scan
        if result == "CONFIG_ERROR":
            break

        if result is not None:
            ping_ms = int(result)
            print(f" -> ✅ SUCCESS! Ping: {ping_ms} ms")
            working_ips.append({"ip": str(ip), "ping": ping_ms})
            
            # --- New Section: Save result to file ---
            result_line = f"IP: {ip}, Ping: {ping_ms} ms\n"
            with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
                f.write(result_line)
            # ------------------------------------

        else:
            print(" -> ❌ FAILED")

    print("\n" + "="*30)
    print(" scanner finished.")

    if working_ips:
        # Sort results by the best ping
        sorted_ips = sorted(working_ips, key=lambda x: x["ping"])
        print(f"\n🏆 Top 5 Working IPs saved in '{RESULTS_FILE}':")
        for item in sorted_ips[:5]:
            print(f"  - IP: {item['ip']:<15} | Ping: {item['ping']} ms")
    else:
        print("😔 No working IPs found in this range.")