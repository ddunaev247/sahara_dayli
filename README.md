1. скачиваем репо, должен быть установлен пайтон, профиль адс также должен быть настрое, работаем только с ММ
2. Устанавливаем завсимости pip install -r requirements.txt
3. Настраиваем файл users.txt, настраваием конфиги в файле main.py
4. Запускаем main.py
5. После первого круга проверяем processed_profiles.txt, если есть профили с ошибкой запускаем софт снова, после 2го круга очищаем этот файл
6. 6. В файле sahara_transactions.py рекомендую менять send_amount = random.uniform(0.000001, 0.000009) диапазон хотя бы иногда, также в главном файле рекомендую ставить другие задержки чтобы не попадать в кластер
