import asyncio
import httpx
from playwright.async_api import async_playwright
import os
import random
from sahara_transactions import get_sahara_rpc, send_sahara_token


ADSP_TOKEN = "ВАШ АДС ТОКЕН"                                 # Настройки AdsPower API
ADSP_API_URL = "http://local.adspower.net:50325/api/v1"
METAMASK_PASSWORD = "ВАШ ПАРОЛЬ МЕТАМАСКА"
PROFILE_ID = ""
MAX_TRANSACTION_ATTEMPTS = 3                # Можно настраивать по желеанию
MAX_PROFILE_START_ATTEMPTS = 2              # Можно настраивать по желеанию
PROFILE_START_TIMEOUT = 15                  # Можно настраивать по желеанию, но не меньше 10 сек
MAX_WALLET_CONNECT_ATTEMPTS = 3             # Можно настраивать по желеанию
DELAY_MIN = 5                               #Минимальная задержка м/у профилями(сек)
DELAY_MAX = 10                              #Максимальная задержка м/у профилями(сек)


METAMASK_URL = "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn/home.html"
TARGET_URL = "https://legends.saharalabs.ai/"
GALXE_URL = "https://app.galxe.com/quest/SaharaAI/GCNLYtpFM5"
BLOG_URL = "https://saharalabs.ai/blog"
TWITTER_URL = "https://x.com/SaharaLabsAI"

LOGIN_BUTTON_SELECTOR = ".login-button"
LOGOUT_BUTTON_SELECTOR = ".logout"

INITIAL_BUTTON_XPATH = '//*[@id="app-content"]/div/div[2]/div/div/button'
GOBI_BUTTON_XPATH = '//*[@id="app"]/div/div/div[5]/div/img'
MODAL_CLOSE_BUTTON_XPATH = '/html/body/div[2]/div/div[2]/div/div[1]/div/button'
VISIT_HUB_XPATH = '/html/body/div[1]/main/div[1]/section/div/div[1]/div/div[3]/div[1]/div[2]/div/div[1]/div'
CONFIRM_BUTTON_XPATH_NEW = '//*[contains(text(), "Continue to Access")]'
VISIT_TWT_XPATH = '/html/body/div[1]/main/div[1]/section/div/div[1]/div/div[3]/div[2]/div[2]/div/div[1]/div'
MODAL_WINDOW_XPATH = '/html/body/div[2]/div/div[2]/div/div[1]/div'
CONNECT_WALLET_XPATH = '/html/body/div[2]/div/div[2]/div/div[1]/div/div/div/div[4]/div'
MM_CONFIRM_XPATH = '//*[@id="app-content"]/div/div/div/div/div[3]/button[2]'
MM_LOGIN_CONFIRM_XPATH = '//*[@id="app-content"]/div/div[2]/div/div/button'

def load_profile_data(file_name='users.txt'):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    child_dir = os.path.join(current_dir, "subfolder")
    possible_paths = [os.path.join(current_dir, file_name), os.path.join(parent_dir, file_name),
                      os.path.join(child_dir, file_name)]
    profiles = []
    for file_path in possible_paths:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and ':' in line:
                            profile_id, address, private_key = line.split(':', 2)
                            profiles.append((profile_id, address, private_key))
                            print(f"Загружен профиль: {profile_id}, адрес: {address}")
                    if profiles:
                        return profiles
                    print(f"Файл {file_path} пуст. Используется фиксированный PROFILE_ID: {PROFILE_ID}")
                    return [(PROFILE_ID, None, None)]
            except Exception as e:
                print(f"Ошибка при чтении файла {file_path}: {e}")
                return [(PROFILE_ID, None, None)]
    print(f"Файл {file_name} не найден. Используется фиксированный PROFILE_ID: {PROFILE_ID}")
    return [(PROFILE_ID, None, None)]

def mark_profile_processed(profile_id, status, file_name='processed_profiles.txt'):
    with open(file_name, 'a') as f:
        f.write(f"{profile_id}:{status}\n")
    print(f"Статус профиля {profile_id}: {status} записан в {file_name}")

def get_profile_status(profile_id, file_name='processed_profiles.txt'):
    if not os.path.exists(file_name):
        return None
    with open(file_name, 'r') as f:
        for line in f:
            if line.strip().startswith(f"{profile_id}:"):
                _, status = line.strip().split(':', 1)
                return status
    return None

async def start_existing_profile(profile_id: str, max_attempts=MAX_PROFILE_START_ATTEMPTS,
                                 timeout=PROFILE_START_TIMEOUT):
    attempt = 1
    while attempt <= max_attempts:
        print(f"ℹ️ Попытка запуска профиля {profile_id} #{attempt}")
        url = f"{ADSP_API_URL}/browser/start"
        headers = {"Authorization": f"Bearer {ADSP_TOKEN}"}
        params = {"user_id": profile_id, "open_tabs": 1, "ip_tab": 0}
        try:
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                response = await client.get(url, headers=headers, params=params)
            response_data = response.json()
            if response_data.get("msg") == "success":
                cdp_url = response_data["data"]["ws"]["puppeteer"]
                print(f"✅ Профиль {profile_id} успешно запущен. CDP-URL: {cdp_url}")
                return cdp_url
            else:
                print(f"❌ Ошибка запуска профиля {profile_id}: {response_data.get('msg')}")
        except asyncio.TimeoutError:
            print(f"❌ Тайм-аут {timeout} секунд превышен при запуске профиля {profile_id}")
        except Exception as e:
            print(f"❌ Ошибка при подключении к API для профиля {profile_id}: {e}")
        if attempt < max_attempts:
            print(f"ℹ️ Повторяем спробу через 5 секунд...")
            await asyncio.sleep(5)
        attempt += 1
    print(f"❌ Не удалось запустить профиль {profile_id} после {max_attempts} попыток")
    mark_profile_processed(profile_id, "failed")
    return None

async def stop_profile(profile_id: str):
    url = f"{ADSP_API_URL}/browser/stop"
    headers = {"Authorization": f"Bearer {ADSP_TOKEN}"}
    params = {"user_id": profile_id}
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            response = await client.get(url, headers=headers, params=params)
        response_data = response.json()
        if response_data.get("msg") == "success":
            print(f"✅ Профиль {profile_id} принудительно закрыт через AdsPower API")
        else:
            print(f"❌ Ошибка принудительного закрытия профиля {profile_id}: {response_data.get('msg')}")
    except Exception as e:
        print(f"❌ Ошибка при вызове API остановки профиля {profile_id}: {e}")

async def connect_wallet_immediately(site_page, context, metamask_page):
    try:
        await site_page.wait_for_selector(f"xpath={MODAL_WINDOW_XPATH}", state="visible", timeout=7000)
        await site_page.wait_for_selector(f"xpath={CONNECT_WALLET_XPATH}", timeout=7000)
        await site_page.click(f"xpath={CONNECT_WALLET_XPATH}")
        print(f"✅ Кнопка 'Connect Wallet' в модальном окне нажата")
        mm_confirm_page = None
        for _ in range(5):
            for page in context.pages:
                if "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn" in page.url and page != metamask_page:
                    mm_confirm_page = page
                    break
            if mm_confirm_page:
                break
            await asyncio.sleep(2)
        if mm_confirm_page:
            await mm_confirm_page.bring_to_front()
            try:
                await mm_confirm_page.wait_for_selector(f"xpath={MM_CONFIRM_XPATH}", timeout=20000)
                await mm_confirm_page.click(f"xpath={MM_CONFIRM_XPATH}")
                print(f"✅ Кнопка 'Confirm' в MetaMask нажата")
                await asyncio.sleep(3)
                await mm_confirm_page.close()
                return True
            except Exception as e:
                print(f"❌ Ошибка при подтверждении в MetaMask: {e}")
                return False
        else:
            print("❌ Страница подтверждения MetaMask не найдена")
            return False
    except Exception as e:
        print(f"❌ Ошибка при немедленном подключении кошелька: {e}")
        return False

async def send_transaction_with_retries(w3, wallet_address, private_key, max_attempts=MAX_TRANSACTION_ATTEMPTS):
    attempt = 1
    while attempt <= max_attempts:
        try:
            success, commission, receipt = send_sahara_token(w3, wallet_address, private_key)
            if success:
                print(f"✅ Транзакция успешно отправлена, комиссия: {commission} SAHARA")
                if receipt:
                    print(f"ℹ️ Хэш транзакции: {receipt.transactionHash.hex()}")
                return True
            else:
                print(f"❌ Не удалось отправить транзакцию на попытке {attempt}")
        except Exception as e:
            print(f"❌ Ошибка при отправке транзакции на попытке {attempt}: {e}")
        if attempt < max_attempts:
            print(f"ℹ️ Повторяем попытку через 5 секунд...")
            await asyncio.sleep(5)
        attempt += 1
    print(f"❌ Все {max_attempts} попыток отправки транзакции провалились")
    return False

async def find_and_close_page(context, url, name, max_attempts=3):
    page = None
    for attempt in range(max_attempts):
        try:
            for p in context.pages:
                if url in p.url:
                    page = p
                    break
            if page:
                print(f"✅ Вкладка {name} найдена на попытке {attempt + 1}")
                await asyncio.sleep(2)
                await page.close()
                print(f"✅ Вкладка {url} закрыта")
                return True
            else:
                print(f"ℹ️ Вкладка {name} не найдена на попытке {attempt + 1}/{max_attempts}")
                await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ Ошибка при поиске вкладки {name} на попытке {attempt + 1}/{max_attempts}: {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(3)
            else:
                print(f"❌ Вкладка {name} не найдена после {max_attempts} попыток")
                raise Exception(f"Не удалось найти вкладку {name}")
    return False

async def handle_profile(profile_id, wallet_address, private_key):
    cdp_url = await start_existing_profile(profile_id)
    if not cdp_url:
        print(f"❌ Не удалось открыть профиль {profile_id} после всех попыток")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]

        try:
            # MetaMask - начальная авторизация
            metamask_page = await context.new_page()
            print(f"✅ Новая страница создана, переходим на {METAMASK_URL}")
            await metamask_page.goto(METAMASK_URL)
            await metamask_page.wait_for_load_state("networkidle", timeout=15000)
            print("✅ MetaMask загружен")
            try:
                await metamask_page.wait_for_selector("input[type='password']", timeout=10000)
                await metamask_page.fill("input[type='password']", METAMASK_PASSWORD)
                print(f"✅ Пароль введен")
                await metamask_page.wait_for_selector(f"xpath={INITIAL_BUTTON_XPATH}", timeout=10000)
                await metamask_page.click(f"xpath={INITIAL_BUTTON_XPATH}")
                print(f"✅ MM login нажата")
                await asyncio.sleep(3)
            except Exception as e:
                print(f"❌ Ошибка при авторизации в MetaMask: {e}")

            # Galxe
            galxe_page = await context.new_page()
            print(f"✅ Новая страница создана, переходим на {GALXE_URL}")
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    await galxe_page.goto(GALXE_URL)
                    await galxe_page.wait_for_load_state("networkidle", timeout=20000)
                    print(f"✅ Страница Galxe загружена")
                    break
                except Exception as e:
                    print(f"❌ Ошибка загрузки Galxe на попытке {attempt + 1}/{max_attempts}: {e}")
                    if attempt < max_attempts - 1:
                        print(f"ℹ️ Повторяем попытку через 5 секунд...")
                        await asyncio.sleep(5)
                    else:
                        raise Exception("Не удалось загрузить страницу Galxe")

            try:
                # Клик на "Visit blog"
                visit_hub_found = False
                for attempt in range(max_attempts):
                    try:
                        await galxe_page.wait_for_selector(f"xpath={VISIT_HUB_XPATH}", timeout=15000)
                        await galxe_page.click(f"xpath={VISIT_HUB_XPATH}")
                        print(f"✅ Кнопка 'Visit blog' нажата")
                        visit_hub_found = True
                        await asyncio.sleep(2)
                        break
                    except Exception as e:
                        print(f"❌ Ошибка при клике на 'Visit blog' на попытке {attempt + 1}/{max_attempts}: {e}")
                        if attempt < max_attempts - 1:
                            print(f"ℹ️ Повторяем попытку через 3 секунд...")
                            await asyncio.sleep(3)
                        else:
                            raise Exception("Не удалось кликнуть 'Visit blog'")

                if not visit_hub_found:
                    raise Exception("Кнопка 'Visit blog' не найдена после всех попыток")

                # Проверка после "Visit blog"
                metamask_button = None
                continue_access_button = None
                max_check_attempts = 3

                for attempt in range(max_check_attempts):
                    try:
                        metamask_button = await galxe_page.query_selector(
                            "xpath=//div[contains(@class, 'ml-3') and (img[contains(@src, '/MetaMask.png')] or .//text()[contains(., 'MetaMask')])]",
                            strict=False
                        )
                        if metamask_button:
                            print(f"✅ Кнопка 'MetaMask' найдена на попытке {attempt + 1}")
                            break
                    except Exception as e:
                        print(f"ℹ️ Кнопка 'MetaMask' не найдена на попытке {attempt + 1}: {e}")

                    try:
                        continue_access_button = await galxe_page.query_selector(f"xpath={CONFIRM_BUTTON_XPATH_NEW}", strict=False)
                        if continue_access_button:
                            print(f"✅ Кнопка 'Continue to Access' найдена на попытке {attempt + 1}")
                            break
                    except Exception as e:
                        print(f"ℹ️ Кнопка 'Continue to Access' не найдена на попытке {attempt + 1}: {e}")

                    if not metamask_button and not continue_access_button and attempt < max_check_attempts - 1:
                        print(f"ℹ️ Ничего не найдено, ждем 3 секунды...")
                        await asyncio.sleep(3)

                # Логика MetaMask
                if metamask_button:
                    print("ℹ️ Обнаружена кнопка MetaMask, выполняем подключение")
                    await metamask_button.click()
                    print(f"✅ Клик по кнопке 'MetaMask' выполнен")
                    await asyncio.sleep(2)

                    mm_confirm_page = None
                    for attempt in range(5):
                        for page in context.pages:
                            if "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn" in page.url and page != metamask_page:
                                mm_confirm_page = page
                                break
                        if mm_confirm_page:
                            break
                        await asyncio.sleep(3)
                        print(f"ℹ️ Поиск окна MetaMask на попытке {attempt + 1}/5")

                    if mm_confirm_page:
                        await mm_confirm_page.bring_to_front()
                        for confirm_attempt in range(max_attempts):
                            try:
                                await mm_confirm_page.wait_for_selector(
                                    "xpath=//button[contains(text(), 'Connect') or contains(text(), 'Připojit')]",
                                    timeout=40000
                                )
                                await mm_confirm_page.click(
                                    "xpath=//button[contains(text(), 'Connect') or contains(text(), 'Připojit')]"
                                )
                                print(f"✅ Кнопка 'Connect' в MetaMask нажата")
                                await asyncio.sleep(3)
                                await mm_confirm_page.close()
                                print("✅ Окно MetaMask закрыто")
                                break
                            except Exception as e:
                                print(f"❌ Ошибка при клике 'Connect' на попытке {confirm_attempt + 1}: {e}")
                                if confirm_attempt < max_attempts - 1:
                                    await asyncio.sleep(3)
                                else:
                                    raise Exception("Не удалось подключить MetaMask")
                    else:
                        raise Exception("Страница MetaMask не найдена")

                    # Повторный клик на "Visit blog"
                    await galxe_page.bring_to_front()
                    for attempt in range(max_attempts):
                        try:
                            await galxe_page.wait_for_selector(f"xpath={VISIT_HUB_XPATH}", timeout=15000)
                            await galxe_page.click(f"xpath={VISIT_HUB_XPATH}")
                            print(f"✅ Повторный клик на 'Visit blog' после MetaMask выполнен")
                            await asyncio.sleep(2)
                            break
                        except Exception as e:
                            print(f"❌ Ошибка при повторном клике на 'Visit blog' на попытке {attempt + 1}: {e}")
                            if attempt < max_attempts - 1:
                                await asyncio.sleep(3)
                            else:
                                raise Exception("Не удалось повторить клик на 'Visit blog'")

                    # Проверка "Continue to Access"
                    for attempt in range(max_attempts):
                        try:
                            continue_access_button = await galxe_page.wait_for_selector(
                                f"xpath={CONFIRM_BUTTON_XPATH_NEW}", timeout=30000, state="visible"
                            )
                            await continue_access_button.click()
                            print(f"✅ Кнопка 'Continue to Access' нажата после MetaMask")
                            await asyncio.sleep(2)
                            break
                        except Exception as e:
                            print(f"❌ Ошибка 'Continue to Access' на попытке {attempt + 1}: {e}")
                            if attempt < max_attempts - 1:
                                await asyncio.sleep(3)
                            else:
                                raise Exception("Не удалось найти или нажать 'Continue to Access'")

                # Логика "Continue to Access"
                elif continue_access_button:
                    await continue_access_button.click()
                    print(f"✅ Кнопка 'Continue to Access' нажата сразу")
                    await asyncio.sleep(3)

                else:
                    raise Exception("Ни MetaMask, ни 'Continue to Access' не найдены")

                # Проверка блога Sahara
                if not await find_and_close_page(context, BLOG_URL, "блога Sahara", max_attempts=3):
                    print("⚠️ Вкладка блога Sahara не найдена")

                # Переход к "Visit Twt"
                await galxe_page.wait_for_selector(f"xpath={VISIT_TWT_XPATH}", timeout=15000)
                await galxe_page.click(f"xpath={VISIT_TWT_XPATH}")
                print(f"✅ Кнопка 'Visit Twt' нажата")
                await asyncio.sleep(3)

                # Проверка Twitter
                if not await find_and_close_page(context, TWITTER_URL, "Twitter", max_attempts=3):
                    print("⚠️ Вкладка Twitter не найдена")

                await galxe_page.close()
                print(f"✅ Страница {GALXE_URL} закрыта")

                # Переход на Sahara
                site_page = None
                for attempt in range(max_attempts):
                    try:
                        site_page = await context.new_page()
                        print(f"✅ Новая страница создана, переходим на {TARGET_URL}")
                        await site_page.goto(TARGET_URL)
                        await site_page.wait_for_load_state("networkidle", timeout=20000)
                        print("✅ Страница Sahara загружена")
                        break
                    except Exception as e:
                        print(f"❌ Ошибка перехода на Sahara на попытке {attempt + 1}/{max_attempts}: {e}")
                        if attempt < max_attempts - 1:
                            print(f"ℹ️ Повторяем попытку через 5 секунд...")
                            await asyncio.sleep(5)
                        else:
                            raise Exception("Не удалось загрузить страницу Sahara")

                await asyncio.sleep(2)

                # Транзакция
                if wallet_address and private_key:
                    print(f"ℹ️ Используется кошелёк: {wallet_address}, профиль: {profile_id}")
                    w3 = get_sahara_rpc()
                    if w3:
                        transaction_success = await send_transaction_with_retries(w3, wallet_address, private_key)
                        if not transaction_success:
                            print("❌ Транзакция не удалась")
                    else:
                        print("❌ Не удалось подключиться к RPC")
                else:
                    print("ℹ️ Данные для транзакции отсутствуют")

                # Подключение кошелька
                wallet_connected = False
                print("ℹ️ Проверяем модальное окно...")
                try:
                    await site_page.wait_for_selector(f"xpath={MODAL_WINDOW_XPATH}", state="visible", timeout=15000)
                    print("ℹ️ Модальное окно найдено")
                    wallet_connected = await connect_wallet_immediately(site_page, context, metamask_page)
                except Exception:
                    print("ℹ️ Модальное окно не найдено, проверяем...")

                if not wallet_connected:
                    attempt = 1
                    while attempt <= MAX_WALLET_CONNECT_ATTEMPTS and not wallet_connected:
                        print(f"ℹ️ Попытка подключения кошелька #{attempt}")
                        try:
                            await site_page.wait_for_selector(LOGIN_BUTTON_SELECTOR, timeout=15000)
                            await site_page.click(LOGIN_BUTTON_SELECTOR)
                            print(f"✅ Кнопка логина нажата")
                            await asyncio.sleep(3)
                            wallet_connected = await connect_wallet_immediately(site_page, context, metamask_page)
                            if not wallet_connected:
                                print("❌ MetaMask не открылся, обновляем страницу...")
                                await site_page.reload()
                                await site_page.wait_for_load_state("networkidle", timeout=20000)
                                print("✅ Страница обновлена")
                        except Exception as e:
                            print(f"❌ Ошибка при клике по кнопке логина: {e}")
                            if attempt < MAX_WALLET_CONNECT_ATTEMPTS:
                                print("ℹ️ Обновляем страницу...")
                                await site_page.reload()
                                await site_page.wait_for_load_state("networkidle", timeout=20000)
                                print("✅ Страница обновлена")
                        attempt += 1

                if not wallet_connected:
                    print("ℹ️ Проверяем застрявший MetaMask...")
                    mm_confirm_page = None
                    for page in context.pages:
                        if "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn" in page.url and page != metamask_page:
                            mm_confirm_page = page
                            break
                    if mm_confirm_page:
                        try:
                            await mm_confirm_page.bring_to_front()
                            await mm_confirm_page.wait_for_selector(f"xpath={MM_CONFIRM_XPATH}", timeout=40000)
                            await mm_confirm_page.click(f"xpath={MM_CONFIRM_XPATH}")
                            print(f"✅ Кнопка 'Confirm' в MetaMask нажата")
                            await asyncio.sleep(3)
                            await mm_confirm_page.close()
                            wallet_connected = True
                        except Exception as e:
                            print(f"❌ Ошибка при обработке MetaMask: {e}")

                if not wallet_connected:
                    print("ℹ️ Проверяем застрявший логин MetaMask...")
                    mm_login_page = None
                    for page in context.pages:
                        if "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn" in page.url and page != metamask_page:
                            mm_login_page = page
                            break
                    if mm_login_page:
                        try:
                            await mm_login_page.bring_to_front()
                            await mm_login_page.wait_for_selector(f"xpath={MM_LOGIN_CONFIRM_XPATH}", timeout=15000)
                            await mm_login_page.click(f"xpath={MM_LOGIN_CONFIRM_XPATH}")
                            print(f"✅ Кнопка логина в MetaMask нажата")
                            await asyncio.sleep(3)
                            await mm_login_page.close()
                            await site_page.reload()
                            await site_page.wait_for_load_state("networkidle", timeout=20000)
                            wallet_connected = True
                        except Exception as e:
                            print(f"❌ Ошибка при обработке логина MetaMask: {e}")

                if not wallet_connected:
                    print(f"❌ Не удалось подключить кошелек после {MAX_WALLET_CONNECT_ATTEMPTS} попыток")
                    for page in context.pages:
                        await page.close()
                    await browser.close()
                    await stop_profile(profile_id)
                    mark_profile_processed(profile_id, "failed")
                    return False

                # Gobi
                try:
                    await site_page.wait_for_selector(f"xpath={GOBI_BUTTON_XPATH}", state="visible", timeout=20000)
                    await site_page.click(f"xpath={GOBI_BUTTON_XPATH}")
                    print(f"✅ Кнопка 'Gobi' нажата")
                    await asyncio.sleep(5)
                    await site_page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception as e:
                    print(f"❌ Ошибка при клике по 'Gobi': {e}")

                # Обработка задач на Sahara
                print("ℹ️ Ожидаем загрузку списка задач...")
                task_list = await site_page.wait_for_selector(".task-list", state="visible", timeout=20000)
                task_buttons = await task_list.query_selector_all(".task-buttons")
                if not task_buttons:
                    print("❌ Элементы 'task-buttons' не найдены")
                else:
                    print(f"ℹ️ Найдено {len(task_buttons)} элементов 'task-buttons'")

                    # Первый проход: кликаем по всем элементам
                    for index, task_button in enumerate(task_buttons, 1):
                        try:
                            div = await task_button.query_selector("div")
                            if div:
                                await div.click()
                                print(f"✅ Клик по div в {index}-м элементе выполнен")
                                await asyncio.sleep(3)  # Задержка между кликами
                            else:
                                print(f"❌ В {index}-м элементе 'task-buttons' не найден div")
                        except Exception as e:
                            print(f"❌ Ошибка при клике по div в {index}-м элементе: {e}")



                    # Второй проход: клеймим
                    for index, task_button in enumerate(task_buttons, 1):
                        try:
                            text = await task_button.inner_text()
                            print(f"ℹ️ Текст {index}-го элемента: '{text}'")
                            if "claim" in text.lower() and "claimed" not in text.lower():
                                div = await task_button.query_selector("div")
                                if div:
                                    await div.click()
                                    print(f"✅ Клик по 'Claim' в {index}-м элементе выполнен")
                                    await asyncio.sleep(3)  # Задержка после клейма
                                else:
                                    print(f"❌ В {index}-м элементе не найден div для 'Claim'")
                            else:
                                print(f"ℹ️ В {index}-м элементе нет 'Claim' или уже 'Claimed': '{text}'")
                        except Exception as e:
                            print(f"❌ Ошибка при проверке или клейме в {index}-м элементе: {e}")

                    # Финальная проверка
                    print("ℹ️ Проверяем финальное состояние задач...")
                    await asyncio.sleep(3)
                    all_claimed = True
                    for index, task_button in enumerate(task_buttons, 1):
                        try:
                            final_text = await task_button.inner_text()
                            print(f"ℹ️ Финальный текст {index}-го элемента: '{final_text}'")
                            if "claimed" not in final_text.lower():
                                all_claimed = False
                        except Exception as e:
                            print(f"❌ Ошибка при финальной проверке {index}-го элемента: {e}")
                            all_claimed = False
                    if all_claimed:
                        print("✅ Все элементы имеют статус 'CLAIMED'")
                    else:
                        print("ℹ️ Не все элементы имеют статус 'Claimed'")

            except Exception as e:
                print(f"❌ Ошибка при выполнении тасков Galxe: {e}")
                raise

        except Exception as e:
            print(f"❌ Ошибка при обработке профиля {profile_id}: {e}")
            for page in context.pages:
                await page.close()
            await browser.close()
            await stop_profile(profile_id)
            mark_profile_processed(profile_id, "failed")
            return False

        for page in context.pages:
            await page.close()
        await browser.close()
        await stop_profile(profile_id)
        mark_profile_processed(profile_id, "success")
        return True

async def main():
    profiles = load_profile_data('users.txt')
    random.shuffle(profiles)

    for profile_id, wallet_address, private_key in profiles:
        profile_status = get_profile_status(profile_id)
        if profile_status == "success":
            print(f"ℹ️ Профиль {profile_id} уже обработан, пропускаем")
            continue
        if profile_status == "failed":
            print(f"ℹ️ Профиль {profile_id} завершился с ошибкой, повторяем")
        else:
            print(f"ℹ️ Профиль {profile_id} не обработан, начинаем")
        print(f"ℹ️ Начинаем обработку профиля {profile_id}")
        success = await handle_profile(profile_id, wallet_address, private_key)
        if not success:
            print(f"❌ Обработка профиля {profile_id} завершилась с ошибкой")

        delay = random.uniform(5, 15)
        print(f"ℹ️ Ожидаем {delay:.2f} секунд перед следующим профилем...")
        await asyncio.sleep(delay)

    print("ℹ️ Все профили обработаны. Нажмите Enter для выхода...")
    input()

if __name__ == "__main__":
    asyncio.run(main())