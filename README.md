## Black Barmen (API clone)

Локальный клон референса `https://bar.antihype.lol`.

- **Порт**: `8000`
- **Формат**: JSON
- **Авторизация**: `Authorization: Bearer <token>`

## Запуск на Windows (PowerShell)

```powershell
cd d:\black-barmen
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Запуск на Windows (cmd.exe)

```bat
cd /d d:\black-barmen
py -m venv .venv
.\.venv\Scripts\activate.bat
py -m pip install -r requirements.txt
py -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Проверка совпадения с референсом (probe.py)

Запустите локальный сервер, затем в другом окне:

```bat
cd /d d:\black-barmen
py probe.py --ref https://bar.antihype.lol --local http://127.0.0.1:8000 --timeout 60 --retries 4
```

Если бывают проблемы с доступом к референсу (TLS handshake timeout), попробуйте:

```bat
py probe.py --ref https://bar.antihype.lol --local http://127.0.0.1:8000 --timeout 60 --retries 4 --insecure
```

## Поиск скрытых эндпоинтов (discover.py)

Референс имеет ограничение по частоте запросов (может отвечать 429 `rate_limit`), поэтому запускайте медленно:

```bat
cd /d d:\black-barmen
py discover.py --ref https://bar.antihype.lol --sleep-ms 1500 --max-requests 30
```

## Найденные секреты

Актуальный список находок записан в `secrets_found.txt`.

