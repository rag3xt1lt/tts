# Black Barmen (API clone)

Запуск на Windows (PowerShell), порт **8000**.

## Установка

```powershell
cd d:\black-barmen
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements.txt
```

## Запуск

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Сравнение с референсом

Запустите сервер локально, затем в другом окне:

```powershell
python .\probe.py --ref https://bar.antihype.lol --local http://127.0.0.1:8000
```

## Поиск скрытых эндпоинтов (референс)

Скрипт делает регистрацию и прогоняет небольшой wordlist по референсу, выводя всё, что не похоже на обычный 404.

```powershell
python .\discover.py --ref https://bar.antihype.lol
```

## Быстрый тест

```powershell
# register
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/register
$token = $r.token

# menu
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/menu -Headers @{
  Authorization = "Bearer $token"
  "X-Time" = "14:30"
}
```

