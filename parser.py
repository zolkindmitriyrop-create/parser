import requests
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup


class CompanyParser:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
    }

    def __init__(self, delay=1.5, max_workers=2, dadata_api_key=None, dadata_secret=None):
        self.delay = delay
        self.max_workers = max_workers
        self.dadata_api_key = dadata_api_key
        self.dadata_secret = dadata_secret
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def parse(self, inn: str, use_dadata: bool = False) -> dict:
        """Главный метод: собирает данные."""
        result = {
            "ИНН": inn,
            "Название": "",
            "Полное название": "",
            "Руководитель": "",
            "Телефон": "",
            "Email": "",
            "Сайт": "",
            "Адрес": "",
            "ОГРН": "",
            "Источник": "",
            "Статус": "Не найдено",
            "Ошибка": ""
        }

        if use_dadata and self.dadata_api_key:
            try:
                data = self._parse_dadata(inn)
                if data and data.get("Название"):
                    result.update(data)
                    result["Статус"] = "Найдено"
                    return result
            except Exception as e:
                result["Ошибка"] = f"DaData: {e}"

        # Локальные источники (работают только с российского IP / локально)
        sources = [
            self._parse_checko,
            self._parse_list_org,
            self._parse_zachestnyibiznes,
            self._parse_audit_it,
        ]

        for source in sources:
            try:
                data = source(inn)
                if data and data.get("Название"):
                    result.update(data)
                    result["Статус"] = "Найдено"
                    break
            except requests.exceptions.ConnectTimeout:
                result["Ошибка"] = "Таймаут соединения. Вероятно, сайт блокирует облачный IP. Запустите локально или используйте DaData API."
                break
            except requests.exceptions.ConnectionError:
                result["Ошибка"] = "Ошибка соединения. Вероятно, сайт блокирует облачный IP. Запустите локально или используйте DaData API."
                break
            except Exception as e:
                result["Ошибка"] = str(e)
                continue
            finally:
                time.sleep(self.delay)

        return result

    # ==================== DADATA API ====================
    def _parse_dadata(self, inn: str) -> dict:
        """Парсинг через DaData API (работает из любой сети)."""
        url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self.dadata_api_key}",
            "X-Secret": self.dadata_secret
        }
        payload = {"query": inn}

        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()

        json_data = resp.json()
        if not json_data.get("suggestions"):
            return {}

        item = json_data["suggestions"][0]["data"]

        phones = []
        emails = []
        if item.get("phones"):
            phones = [p["value"] for p in item["phones"] if p.get("value")]
        if item.get("emails"):
            emails = [e["value"] for e in item["emails"] if e.get("value")]

        # Руководитель
        manager = ""
        if item.get("management"):
            manager = item["management"].get("name", "")
        elif item.get("founders"):
            manager = item["founders"][0].get("name", "")

        return {
            "Название": item.get("name", {}).get("short", ""),
            "Полное название": item.get("name", {}).get("full", ""),
            "Руководитель": manager,
            "Телефон": "; ".join(phones) if phones else "",
            "Email": "; ".join(emails) if emails else "",
            "Адрес": item.get("address", {}).get("value", ""),
            "ОГРН": item.get("ogrn", ""),
            "Источник": "dadata.ru"
        }

    # ==================== ЛОКАЛЬНЫЕ ИСТОЧНИКИ ====================
    def _parse_checko(self, inn: str) -> dict:
        url = f"https://checko.com/company/{inn}"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {}

        title = soup.find("h1")
        if title:
            data["Название"] = title.get_text(strip=True)

        phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', resp.text)
        if phones:
            data["Телефон"] = "; ".join(sorted(set(phones)))

        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
        if emails:
            data["Email"] = "; ".join(sorted(set(emails)))

        addr = soup.find(text=re.compile("Юридический адрес"))
        if addr and addr.find_next():
            data["Адрес"] = addr.find_next().get_text(strip=True)

        data["Источник"] = "checko.com"
        return data

    def _parse_list_org(self, inn: str) -> dict:
        url = f"https://list-org.com/search?type=inn&val={inn}"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {}

        link = soup.find("a", href=re.compile(r"/company/\d+"))
        if link:
            card_url = "https://list-org.com" + link["href"]
            resp2 = self.session.get(card_url, timeout=15)
            soup2 = BeautifulSoup(resp2.text, "html.parser")

            h1 = soup2.find("h1")
            if h1:
                data["Название"] = h1.get_text(strip=True)

            phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', resp2.text)
            if phones:
                data["Телефон"] = "; ".join(sorted(set(phones)))

            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp2.text)
            if emails:
                data["Email"] = "; ".join(sorted(set(emails)))

            data["Источник"] = "list-org.com"

        return data

    def _parse_zachestnyibiznes(self, inn: str) -> dict:
        url = f"https://zachestnyibiznes.ru/search?query={inn}"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {}

        link = soup.find("a", href=re.compile(r"/company/"))
        if link:
            card_url = "https://zachestnyibiznes.ru" + link["href"]
            resp2 = self.session.get(card_url, timeout=15)
            soup2 = BeautifulSoup(resp2.text, "html.parser")

            title = soup2.find("h1")
            if title:
                data["Название"] = title.get_text(strip=True)

            for row in soup2.find_all("div", class_=re.compile("row")):
                text = row.get_text()
                if "Телефон" in text or "тел." in text:
                    phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text)
                    if phones:
                        data["Телефон"] = "; ".join(sorted(set(phones)))

            data["Источник"] = "zachestnyibiznes.ru"

        return data

    def _parse_audit_it(self, inn: str) -> dict:
        url = f"https://www.audit-it.ru/inform/{inn}/"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {}

        title = soup.find("h1")
        if title:
            data["Название"] = title.get_text(strip=True)

        phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', resp.text)
        if phones:
            data["Телефон"] = "; ".join(sorted(set(phones)))

        data["Источник"] = "audit-it.ru"
        return data
