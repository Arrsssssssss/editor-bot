import logging
import os
from datetime import datetime

import gspread
import pytz

logger = logging.getLogger(__name__)

TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# Column indices (0-based in Python list; Sheets API uses 1-based)
COL_DATE = 0
COL_DAY = 1
COL_COLLECTION = 2
COL_DESCRIPTION = 3
COL_PLATFORM = 4
COL_STATUS = 5


class SheetsError(Exception):
    pass


class SheetsClient:
    def __init__(self):
        self._creds_file = os.getenv("GOOGLE_CREDS_FILE", "creds.json")
        self._sheet_id = os.environ["GOOGLE_SHEET_ID"]
        self._sheet = None

    @property
    def sheet(self):
        if self._sheet is None:
            self._connect()
        return self._sheet

    def _connect(self):
        try:
            gc = gspread.service_account(filename=self._creds_file)
            self._sheet = gc.open_by_key(self._sheet_id).sheet1
        except Exception as e:
            raise SheetsError(f"Не удалось подключиться к Google Sheets: {e}") from e

    def _reset(self):
        self._sheet = None

    def _get(self, row: list, col: int) -> str:
        try:
            return row[col].strip()
        except (IndexError, AttributeError):
            return ""

    def get_tasks_for_today(self) -> list[tuple[int, dict]]:
        """Return [(row_1based, task_dict), ...] for today's date."""
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).strftime("%d.%m.%Y")

        try:
            rows = self.sheet.get_all_values()
        except Exception as e:
            self._reset()
            raise SheetsError(f"Ошибка чтения таблицы: {e}") from e

        tasks = []
        for i, row in enumerate(rows):
            if self._get(row, COL_DATE) != today:
                continue
            tasks.append((
                i + 1,  # 1-based row index for Sheets API
                {
                    "date":        self._get(row, COL_DATE),
                    "day":         self._get(row, COL_DAY),
                    "collection":  self._get(row, COL_COLLECTION),
                    "description": self._get(row, COL_DESCRIPTION),
                    "platform":    self._get(row, COL_PLATFORM),
                    "status":      self._get(row, COL_STATUS),
                },
            ))
        return tasks

    def mark_as_done(self, row_index: int) -> dict:
        """Set status = 'Готово' for the given 1-based row. Returns updated task dict."""
        try:
            row = self.sheet.row_values(row_index)
            self.sheet.update_cell(row_index, COL_STATUS + 1, "Готово")
        except Exception as e:
            self._reset()
            raise SheetsError(f"Ошибка обновления строки {row_index}: {e}") from e

        return {
            "date":        self._get(row, COL_DATE),
            "day":         self._get(row, COL_DAY),
            "collection":  self._get(row, COL_COLLECTION),
            "description": self._get(row, COL_DESCRIPTION),
            "platform":    self._get(row, COL_PLATFORM),
            "status":      "Готово",
        }

    def get_month_status(self) -> dict:
        """Return statistics for the current calendar month."""
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        current_month_year = now.strftime("%m.%Y")  # e.g. "06.2026"

        try:
            rows = self.sheet.get_all_values()
        except Exception as e:
            self._reset()
            raise SheetsError(f"Ошибка чтения таблицы: {e}") from e

        total = done = published = in_progress = 0

        for row in rows:
            date_str = self._get(row, COL_DATE)
            if not date_str:
                continue
            parts = date_str.split(".")
            if len(parts) != 3:
                continue
            if f"{parts[1]}.{parts[2]}" != current_month_year:
                continue

            total += 1
            status = self._get(row, COL_STATUS)
            if status == "Готово":
                done += 1
            elif status == "Выложено":
                published += 1
            else:
                in_progress += 1

        return {
            "total":       total,
            "done":        done,
            "published":   published,
            "in_progress": in_progress,
        }
