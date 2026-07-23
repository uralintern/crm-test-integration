import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from models.internship import Internship
from utils.internships_db import internships_db
from utils.export import get_export_csv, get_export_excel, get_export_word, _get_rows
from app.schemas import (
    InternshipsListResponse,
    InternshipDetailResponse,
    InternshipListItem,
    PaginationMeta,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def get_session() -> Session:
    return internships_db._get_session()


@router.get(
    "/internship",
    response_model=InternshipsListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Успешный ответ со списком стажировок",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "title": "Python Developer",
                                "direction": "Разработка",
                                "company": "Яндекс",
                                "city": "Москва",
                                "work_format": "Гибрид",
                                "link": "https://example.com/vacancy/1",
                                "salary_from": 50000,
                                "description": "Разработка бэкенда"
                            }
                        ],
                        "pagination": {
                            "total": 139,
                            "page": 1,
                            "page_size": 20,
                            "total_pages": 7
                        }
                    }
                }
            }
        }
    }
)
async def get_internships(
    page: int = Query(1, ge=1, description="Номер страницы для пагинации"),
    city: Optional[list[str]] = Query(None, description="Город (можно передавать несколько)"),
    format: Optional[list[str]] = Query(None, description="Формат работы (office, hybrid, remote)"),
    employment: Optional[list[str]] = Query(None, description="Занятость (full-time, part-time)"),
) -> InternshipsListResponse:
    session = None
    try:
        session = get_session()
        query = session.query(Internship)

        if city:
            query = query.filter(Internship.city.in_(city))

        if format:
            format_mapping = {
                'office': 'Офис',
                'hybrid': 'Гибрид',
                'remote': 'Удалённая работа'
            }
            mapped_formats = [format_mapping.get(f, f) for f in format]
            query = query.filter(Internship.work_format.in_(mapped_formats))

        if employment:
            pass

        total = query.count()
        page_size = DEFAULT_PAGE_SIZE
        skip = (page - 1) * page_size
        internships = query.offset(skip).limit(page_size).all()
        data = [
            InternshipListItem(
                id=internship.id,
                title=internship.title,
                direction=internship.direction,
                company=internship.company,
                city=internship.city,
                work_format=internship.work_format,
                link=internship.link,
                salary_from=internship.salary_from,
                description=internship.description
            )
            for internship in internships
        ]

        total_pages = (total + page_size - 1) // page_size
        pagination = PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

        logger.info(f"Retrieved {len(data)} internships from page {page}, total: {total}")
        return InternshipsListResponse(data=data, pagination=pagination)

    except Exception as e:
        logger.error(f"Error retrieving internships: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
    finally:
        if session:
            session.close()


@router.get(
    "/internship/export",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Экспорт стажировок в файл",
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
            },
        },
        400: {"description": "Некорректный формат"},
        500: {"description": "Ошибка сервера"},
    },
)
async def export_internships(
    format: str = Query(
        ...,
        regex="^(csv|word|excel)$",
        description="Формат файла: csv, word или excel",
    )
):
    session = None
    try:
        session = get_session()
        rows = _get_rows(session)

        if format == "csv":
            buf = get_export_csv(rows)
            media_type = "text/csv; charset=utf-8"
            filename = "internships.csv"
        elif format == "word":
            buf = get_export_word(rows)
            media_type = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            filename = "internships.docx"
        else:
            buf = get_export_excel(rows)
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            filename = "internships.xlsx"

        return Response(
            content=buf.getvalue(),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error exporting internships: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
    finally:
        if session:
            session.close()


@router.get(
    "/internship/{internship_uuid}",
    response_model=InternshipDetailResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Полная информация о стажировке",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Python Developer",
                        "direction": "Разработка",
                        "company": "Яндекс",
                        "city": "Москва",
                        "work_format": "Гибрид",
                        "link": "https://example.com/vacancy/1",
                        "salary_from": 50000,
                        "description": "Разработка бэкенда на Python"
                    }
                }
            }
        },
        404: {
            "description": "Стажировка не найдена",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Internship not found",
                        "status_code": 404
                    }
                }
            }
        }
    }
)
async def get_internship_by_uuid(internship_uuid: UUID) -> InternshipDetailResponse:
    session = None
    try:
        session = get_session()
        internship = session.query(Internship).filter(
            Internship.id == internship_uuid
        ).first()

        if not internship:
            logger.warning(f"Internship not found: {internship_uuid}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Internship not found"
            )

        logger.info(f"Retrieved internship: {internship_uuid}")
        return InternshipDetailResponse(
            id=internship.id,
            title=internship.title,
            direction=internship.direction,
            company=internship.company,
            city=internship.city,
            work_format=internship.work_format,
            link=internship.link,
            salary_from=internship.salary_from,
            description=internship.description
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error retrieving internship {internship_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
    finally:
        if session:
            session.close()
