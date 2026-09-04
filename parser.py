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
    }

    def __init__(self, delay=1.0, max_workers=3):
        self.delay = delay
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def parse(self, inn: str) -> dict:
        """Главный метод: собирает данные со всех источников."""
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
            "Статус": "Не найдено"
        }

        # Пробуем источники по очереди
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
            except Exception:
                continue
            finally:
                time.sleep(self.delay)

        return result

    def _parse_checko(self, inn: str) -> dict:
        """Парсинг checko.com"""
        url = f"https://checko.com/company/{inn}"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {}

        # Название
        title = soup.find("h1")
        if title:
            data["Название"] = title.get_text(strip=True)

        # Телефон
        phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', resp.text)
        if phones:
            data["Телефон"] = "; ".join(sorted(set(phones)))

        # Email
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
        if emails:
            data["Email"] = "; ".join(sorted(set(emails)))

        # Адрес
        addr = soup.find(text=re.compile("Юридический адрес"))
        if addr and addr.find_next():
            data["Адрес"] = addr.find_next().get_text(strip=True)

        data["Источник"] = "checko.com"
        return data

    def _parse_list_org(self, inn: str) -> dict:
        """Парсинг list-org.com"""
        url = f"https://list-org.com/search?type=inn&val={inn}"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {}

        # Ищем ссылку на карточку
        link = soup.find("a", href=re.compile(r"/company/\d+"))
        if link:
            card_url = "https://list-org.com" + link["href"]
            resp2 = self.session.get(card_url, timeout=15)
            soup2 = BeautifulSoup(resp2.text, "html.parser")

            # Название
            h1 = soup2.find("h1")
            if h1:
                data["Название"] = h1.get_text(strip=True)

            # Телефон
            phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', resp2.text)
            if phones:
                data["Телефон"] = "; ".join(sorted(set(phones)))

            # Email
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp2.text)
            if emails:
                data["Email"] = "; ".join(sorted(set(emails)))

            data["Источник"] = "list-org.com"

        return data

    def _parse_zachestnyibiznes(self, inn: str) -> dict:
        """Парсинг zachestnyibiznes.ru"""
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

            # Ищем блоки с данными
            for row in soup2.find_all("div", class_=re.compile("row")):
                text = row.get_text()
                if "Телефон" in text or "тел." in text:
                    phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text)
                    if phones:
                        data["Телефон"] = "; ".join(sorted(set(phones)))

            data["Источник"] = "zachestnyibiznes.ru"

        return data

    def _parse_audit_it(self, inn: str) -> dict:
        """Парсинг audit-it.ru"""
        url = f"https://www.audit-it.ru/inform/{inn}/"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {}

        title = soup.find("h1")
        if title:
            data["Название"] = title.get_text(strip=True)

        # Телефон
        phones = re.findall(r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', resp.text)
        if phones:
            data["Телефон"] = "; ".join(sorted(set(phones)))

        data["Источник"] = "audit-it.ru"
        return data

    def parse_batch(self, inns: list) -> list:
        """Параллельный парсинг списка ИНН."""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_inn = {executor.submit(self.parse, inn): inn for inn in inns}
            for future in as_completed(future_to_inn):
                results.append(future.result())
        return results
