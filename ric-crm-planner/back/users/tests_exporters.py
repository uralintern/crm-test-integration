"""Характеризационные тесты экспорта мероприятия (docx) и заявок (xlsx).

Фиксируют текущее поведение эндпоинтов:
- GET /api/users/events/<id>/export/details.docx/
- GET /api/users/events/<id>/export/applications.xlsx/
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone
from io import BytesIO
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from docx import Document
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.test import APIClient

from users.exporters import (
    _content_disposition,
    _format_date,
    _format_datetime,
    _normalize_form_fields,
    _safe_filename,
    _stringify,
)
from users.models import (
    Application,
    Direction,
    Event,
    EventSpecialization,
    Project,
    Specialization,
    Status,
)

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

BASE_XLSX_HEADERS = [
    "ID заявки",
    "ФИО",
    "Email",
    "VK",
    "Университет",
    "Курс",
    "Мероприятие",
    "Направление",
    "Проект",
    "Специализация",
    "Текущий статус",
    "ID команды",
    "Тесты назначены",
    "Сессия тестирования",
    "Дата подачи",
    "Срок заявки",
    "Комментарий организатора",
]


def _docx_text(content: bytes) -> str:
    """Весь текст документа: абзацы и ячейки таблиц."""
    document = Document(BytesIO(content))
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def _docx_table_rows(content: bytes) -> list[list[str]]:
    document = Document(BytesIO(content))
    rows = []
    for table in document.tables:
        for row in table.rows:
            rows.append([cell.text for cell in row.cells])
    return rows


class ExportTestDataMixin:
    password = "StrongPass123"

    def create_user(self, email, first_name="", last_name="", **extra):
        return get_user_model().objects.create_user(
            email=email,
            username=email,
            password=self.password,
            first_name=first_name,
            last_name=last_name,
            **extra,
        )

    def create_event(self, name="Летняя школа", **extra):
        defaults = {
            "description": "",
            "stage": "Набор",
            "start_date": date(2026, 6, 1),
            "end_date": date(2026, 6, 30),
            "end_app_date": datetime(2026, 5, 20, 18, 0, tzinfo=dt_timezone.utc),
        }
        defaults.update(extra)
        return Event.objects.create(name=name, **defaults)


class EventExportPermissionTests(ExportTestDataMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = self.create_user("leader@example.test", "Лид", "Лидеров")
        self.organizer = self.create_user("organizer@example.test", "Орг", "Оргов")
        self.student = self.create_user("student@example.test", "Студ", "Студентов")
        self.superuser = get_user_model().objects.create_superuser(
            email="admin@example.test",
            username="admin@example.test",
            password=self.password,
        )
        self.event = self.create_event(leader=self.leader)
        self.event.organizers.add(self.organizer)

    def details_url(self, event_id=None):
        return reverse("event-export-details-docx", kwargs={"event_id": event_id or self.event.id})

    def applications_url(self, event_id=None):
        return reverse("event-export-applications-xlsx", kwargs={"event_id": event_id or self.event.id})

    def test_urls_are_stable(self):
        self.assertEqual(self.details_url(), f"/api/users/events/{self.event.id}/export/details.docx/")
        self.assertEqual(self.applications_url(), f"/api/users/events/{self.event.id}/export/applications.xlsx/")

    def test_anonymous_user_gets_401(self):
        self.assertEqual(self.client.get(self.details_url()).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.applications_url()).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_projectant_without_event_access_gets_403(self):
        self.client.force_authenticate(user=self.student)

        details = self.client.get(self.details_url())
        applications = self.client.get(self.applications_url())

        self.assertEqual(details.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(details.data["detail"], "Недостаточно прав для экспорта мероприятия.")
        self.assertEqual(applications.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(applications.data["detail"], "Недостаточно прав для экспорта заявок.")

    def test_missing_event_returns_404(self):
        self.client.force_authenticate(user=self.superuser)

        self.assertEqual(self.client.get(self.details_url(event_id=999999)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get(self.applications_url(event_id=999999)).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_event_leader_can_export_both_documents(self):
        self.client.force_authenticate(user=self.leader)

        details = self.client.get(self.details_url())
        applications = self.client.get(self.applications_url())

        self.assertEqual(details.status_code, status.HTTP_200_OK)
        self.assertEqual(details["Content-Type"], DOCX_CONTENT_TYPE)
        self.assertEqual(applications.status_code, status.HTTP_200_OK)
        self.assertEqual(applications["Content-Type"], XLSX_CONTENT_TYPE)

    def test_event_organizer_can_export(self):
        self.client.force_authenticate(user=self.organizer)

        self.assertEqual(self.client.get(self.details_url()).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(self.applications_url()).status_code, status.HTTP_200_OK)

    def test_superuser_can_export(self):
        self.client.force_authenticate(user=self.superuser)

        self.assertEqual(self.client.get(self.details_url()).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(self.applications_url()).status_code, status.HTTP_200_OK)


class EventDetailsDocxExportTests(ExportTestDataMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = self.create_user("leader@example.test", "Анна", "Иванова")
        self.organizer = self.create_user("organizer@example.test", "Борис", "Петров")
        self.curator = self.create_user("curator@example.test", "Вера", "Сидорова")
        self.student = self.create_user("student@example.test", "Глеб", "Смирнов")

        self.spec_backend = Specialization.objects.create(name="Backend")
        self.spec_design = Specialization.objects.create(name="Дизайн")

        self.event = self.create_event(
            name="Летняя школа 2026",
            description="Первая строка\n\nВторая строка",
            leader=self.leader,
            org_chat_url="https://vk.example.test/chat",
            org_chat_peer_id=2000000001,
            application_form_fields=[
                {"id": "portfolio", "label": "Портфолио", "type": "select", "required": True, "options": ["Да", " Нет "]},
            ],
        )
        self.event.organizers.add(self.organizer)
        EventSpecialization.objects.create(event=self.event, specialization=self.spec_backend)
        EventSpecialization.objects.create(event=self.event, specialization=self.spec_design)

        self.direction_with_projects = Direction.objects.create(
            name="Аналитика", description="Описание аналитики", event=self.event
        )
        self.direction_empty = Direction.objects.create(name="Веб", event=self.event)
        Project.objects.create(
            direction=self.direction_with_projects,
            name="Дашборд",
            description="Сбор метрик",
            curator=self.curator,
            teams=3,
        )

        self.status_sent = Status.objects.create(name="Тестовый статус экспорта А")
        now = timezone.now()
        for user in (self.student, self.curator):
            Application.objects.create(
                user=user, event=self.event, status=self.status_sent, date_sub=now, date_end=now + timedelta(days=1)
            )
        Application.objects.create(user=self.organizer, event=self.event, date_sub=now, date_end=now)

        self.client.force_authenticate(user=self.leader)

    def get_docx(self, event=None):
        event = event or self.event
        return self.client.get(reverse("event-export-details-docx", kwargs={"event_id": event.id}))

    def test_response_headers(self):
        response = self.get_docx()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], DOCX_CONTENT_TYPE)
        self.assertEqual(response["Cache-Control"], "no-store")
        disposition = response["Content-Disposition"]
        self.assertTrue(disposition.startswith('attachment; filename="'))
        self.assertIn(f"filename*=UTF-8''{quote('Летняя_школа_2026_данные_мероприятия.docx')}", disposition)

    def test_document_contains_main_info(self):
        content = self.get_docx().content
        rows = _docx_table_rows(content)
        info = {row[0]: row[1] for row in rows if len(row) == 2}

        self.assertEqual(info["Название"], "Летняя школа 2026")
        self.assertEqual(info["Этап"], "Набор")
        self.assertEqual(info["Дата начала"], "01.06.2026")
        self.assertEqual(info["Дата завершения"], "30.06.2026")
        self.assertEqual(info["Срок приема заявок"], "20.05.2026 18:00")
        # Организаторы из M2M (лидер в этом случае не добавляется).
        self.assertEqual(info["Организаторы"], "Петров Борис")
        # Порядок специализаций в коде не задан (нет order_by), сравниваем без учёта порядка.
        self.assertEqual(sorted(info["Специализации"].split(", ")), ["Backend", "Дизайн"])
        self.assertEqual(info["Ссылка на орг. чат VK"], "https://vk.example.test/chat")
        self.assertEqual(info["ID беседы VK"], "2000000001")

    def test_document_contains_description_directions_and_projects(self):
        content = self.get_docx().content
        text = _docx_text(content)
        rows = _docx_table_rows(content)

        self.assertIn("Первая строка", text)
        self.assertIn("Вторая строка", text)
        self.assertIn("Аналитика", text)
        self.assertIn("Описание аналитики", text)
        self.assertIn("Веб", text)
        self.assertIn("Проекты не добавлены.", text)
        self.assertIn(["Проект", "Куратор", "Команд", "Описание"], rows)
        self.assertIn(["Дашборд", "Сидорова Вера", "3", "Сбор метрик"], rows)

    def test_document_contains_application_statistics(self):
        content = self.get_docx().content
        text = _docx_text(content)
        rows = _docx_table_rows(content)

        self.assertIn("Всего заявок: 3", text)
        self.assertIn(["Статус", "Количество"], rows)
        self.assertIn(["Тестовый статус экспорта А", "2"], rows)
        self.assertIn(["Без статуса", "1"], rows)

    def test_document_contains_form_fields_table(self):
        rows = _docx_table_rows(self.get_docx().content)
        form_rows = rows[rows.index(["Поле", "Тип", "Обязательное", "Варианты"]) + 1 :]
        labels = [row[0] for row in form_rows]

        # Системные поля всегда добавляются и идут первыми в фиксированном порядке.
        self.assertEqual(
            labels,
            ["ФИО", "Аккаунт VK", "Университет", "Курс", "Специализация", "О себе", "Портфолио"],
        )
        self.assertIn(["Портфолио", "Выпадающий список", "Да", "Да, Нет"], form_rows)
        self.assertIn(["О себе", "Длинный текст", "Нет", ""], form_rows)
        self.assertIn(["ФИО", "Короткий текст", "Да", ""], form_rows)

    def test_empty_event_uses_fallback_texts(self):
        empty_event = self.create_event(
            name="Пустое",
            leader=self.leader,
            specialization=self.spec_backend,
        )

        content = self.get_docx(empty_event).content
        text = _docx_text(content)
        info = {row[0]: row[1] for row in _docx_table_rows(content) if len(row) == 2}

        self.assertIn("Описание не заполнено.", text)
        self.assertIn("Направления не добавлены.", text)
        self.assertIn("Всего заявок: 0", text)
        # Без организаторов в M2M выводится лидер.
        self.assertEqual(info["Организаторы"], "Иванова Анна")
        # Без EventSpecialization берётся старое поле Event.specialization.
        self.assertEqual(info["Специализации"], "Backend")
        self.assertEqual(info["ID беседы VK"], "")


class EventApplicationsXlsxExportTests(ExportTestDataMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = self.create_user("leader@example.test", "Анна", "Иванова")
        self.student = self.create_user("student@example.test", "Глеб", "Смирнов")
        self.second_student = self.create_user("second@example.test")

        profile = self.student.crm_profile
        profile.patronymic = "Олегович"
        profile.vk = "https://vk.com/id1"
        profile.university = "Тестовый университет"
        profile.course = 3
        profile.save()

        self.event = self.create_event(
            name="Хакатон / Осень!",
            leader=self.leader,
            application_form_fields=[{"id": "portfolio", "label": "Портфолио"}],
        )
        self.direction = Direction.objects.create(name="Аналитика", event=self.event)
        self.project = Project.objects.create(direction=self.direction, name="Дашборд")
        self.specialization = Specialization.objects.create(name="Backend")
        self.status = Status.objects.create(name="Тестовый статус экспорта Б")

        self.first = Application.objects.create(
            user=self.student,
            event=self.event,
            direction=self.direction,
            project=self.project,
            specialization=self.specialization,
            status=self.status,
            team_id=17,
            tests_assigned=True,
            test_session_id="session-1",
            comment="Хороший кандидат",
            custom_fields={"portfolio": "https://example.test/portfolio", "extra_key": ["a", "b"]},
            date_sub=datetime(2026, 1, 15, 10, 30, tzinfo=dt_timezone.utc),
            date_end=datetime(2026, 1, 20, 9, 0, tzinfo=dt_timezone.utc),
        )
        self.second = Application.objects.create(
            user=self.second_student,
            event=self.event,
            custom_fields={},
            date_sub=datetime(2026, 1, 16, 8, 0, tzinfo=dt_timezone.utc),
            date_end=datetime(2026, 1, 20, 9, 0, tzinfo=dt_timezone.utc),
        )
        # Заявка другого мероприятия не должна попасть в выгрузку.
        other_event = self.create_event(name="Другое", leader=self.leader)
        Application.objects.create(
            user=self.student,
            event=other_event,
            date_sub=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            date_end=datetime(2026, 1, 2, tzinfo=dt_timezone.utc),
        )

        self.client.force_authenticate(user=self.leader)

    def get_sheet(self):
        response = self.client.get(
            reverse("event-export-applications-xlsx", kwargs={"event_id": self.event.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workbook = load_workbook(BytesIO(response.content))
        return response, workbook["Заявки"]

    def rows_as_dicts(self, sheet):
        rows = list(sheet.iter_rows(values_only=True))
        headers = list(rows[0])
        return headers, [dict(zip(headers, row)) for row in rows[1:]]

    def test_response_headers(self):
        response, _ = self.get_sheet()

        self.assertEqual(response["Content-Type"], XLSX_CONTENT_TYPE)
        self.assertEqual(response["Cache-Control"], "no-store")
        # Спецсимволы из названия вырезаются, пробелы заменяются на "_".
        self.assertIn(
            f"filename*=UTF-8''{quote('Хакатон_Осень_заявки.xlsx')}",
            response["Content-Disposition"],
        )

    def test_headers_include_base_and_custom_columns(self):
        _, sheet = self.get_sheet()
        headers, _ = self.rows_as_dicts(sheet)

        self.assertEqual(headers[: len(BASE_XLSX_HEADERS)], BASE_XLSX_HEADERS)
        # После базовых: поля формы (кроме системных), затем ключи из ответов, которых нет в форме.
        self.assertEqual(headers[len(BASE_XLSX_HEADERS) :], ["О себе", "Портфолио", "Доп. поле: extra_key"])
        self.assertEqual(sheet.freeze_panes, "A2")

    def test_rows_contain_only_event_applications_in_submission_order(self):
        _, sheet = self.get_sheet()
        _, rows = self.rows_as_dicts(sheet)

        self.assertEqual([row["ID заявки"] for row in rows], [str(self.first.id), str(self.second.id)])

    def test_full_row_values(self):
        _, sheet = self.get_sheet()
        _, rows = self.rows_as_dicts(sheet)
        row = rows[0]

        self.assertEqual(row["ФИО"], "Смирнов Глеб Олегович")
        self.assertEqual(row["Email"], "student@example.test")
        self.assertEqual(row["VK"], "https://vk.com/id1")
        self.assertEqual(row["Университет"], "Тестовый университет")
        self.assertEqual(row["Курс"], "3")
        self.assertEqual(row["Мероприятие"], "Хакатон / Осень!")
        self.assertEqual(row["Направление"], "Аналитика")
        self.assertEqual(row["Проект"], "Дашборд")
        self.assertEqual(row["Специализация"], "Backend")
        self.assertEqual(row["Текущий статус"], "Тестовый статус экспорта Б")
        self.assertEqual(row["ID команды"], "17")
        self.assertEqual(row["Тесты назначены"], "Да")
        self.assertEqual(row["Сессия тестирования"], "session-1")
        self.assertEqual(row["Дата подачи"], "15.01.2026 10:30")
        self.assertEqual(row["Срок заявки"], "20.01.2026 09:00")
        self.assertEqual(row["Комментарий организатора"], "Хороший кандидат")
        self.assertEqual(row["Портфолио"], "https://example.test/portfolio")
        self.assertEqual(row["Доп. поле: extra_key"], "a, b")

    def test_sparse_row_values(self):
        _, sheet = self.get_sheet()
        _, rows = self.rows_as_dicts(sheet)
        row = rows[1]

        # У пользователя без ФИО в профиле выводится email.
        self.assertEqual(row["ФИО"], "second@example.test")
        self.assertEqual(row["Тесты назначены"], "Нет")
        for column in ("Направление", "Проект", "Специализация", "Текущий статус", "ID команды", "Портфолио"):
            self.assertIn(row[column], (None, ""), column)


class ExporterHelperTests(TestCase):
    def test_stringify(self):
        self.assertEqual(_stringify(None), "")
        self.assertEqual(_stringify(True), "Да")
        self.assertEqual(_stringify(False), "Нет")
        self.assertEqual(_stringify(date(2026, 3, 1)), "01.03.2026")
        self.assertEqual(_stringify(datetime(2026, 3, 1, 7, 5)), "01.03.2026 07:05")
        self.assertEqual(_stringify(["a", None, "", 2]), "a, 2")
        self.assertEqual(_stringify({"a": 1, "b": True}), "a: 1; b: Да")
        self.assertEqual(_stringify(5), "5")

    def test_format_date_and_datetime(self):
        self.assertEqual(_format_date(None), "")
        self.assertEqual(_format_date(datetime(2026, 3, 1, 23, 0, tzinfo=dt_timezone.utc)), "01.03.2026")
        self.assertEqual(_format_date("raw"), "raw")
        self.assertEqual(_format_datetime(None), "")
        self.assertEqual(_format_datetime("raw"), "raw")

    def test_safe_filename(self):
        self.assertEqual(_safe_filename("Мой  проект: 2026", "x.docx"), "Мой_проект_2026_x.docx")
        self.assertEqual(_safe_filename("", "x.docx"), "event_x.docx")
        self.assertEqual(_safe_filename("!!!", "x.docx"), "event_x.docx")
        self.assertEqual(len(_safe_filename("a" * 200, "x.docx")), 80 + len("_x.docx"))

    def test_content_disposition_has_ascii_fallback_and_utf8_name(self):
        value = _content_disposition("отчёт.xlsx")

        self.assertEqual(value, f"attachment; filename=\"_.xlsx\"; filename*=UTF-8''{quote('отчёт.xlsx')}")

    def test_normalize_form_fields_skips_invalid_and_duplicates(self):
        fields = _normalize_form_fields(
            [
                "not-a-dict",
                {"id": ""},
                {"id": "x", "label": "Икс", "type": "unknown", "options": "not-a-list"},
                {"id": "x", "label": "Дубль"},
                {"id": "course", "label": "Год обучения", "required": False},
            ]
        )
        by_id = {field["id"]: field for field in fields}

        self.assertEqual(
            [field["id"] for field in fields],
            ["studentName", "telegram", "university", "course", "specialization", "about", "x"],
        )
        self.assertEqual(by_id["x"], {"id": "x", "label": "Икс", "type": "text", "required": False, "options": []})
        # Переданное системное поле сохраняет свою подпись и флаг.
        self.assertEqual(by_id["course"]["label"], "Год обучения")
        self.assertFalse(by_id["course"]["required"])

    def test_normalize_form_fields_with_non_list_input(self):
        fields = _normalize_form_fields(None)

        self.assertEqual(len(fields), 6)
        self.assertTrue(all(field["required"] for field in fields if field["id"] != "about"))
