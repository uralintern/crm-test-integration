"""
Маршруты для API стажировок
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException, status
from sqlalchemy.orm import Session

from models.internship import Internship
from utils.internships_db import internships_db
from app.schemas import (
    InternshipsListResponse,
    InternshipDetailResponse,
    InternshipListItem,
    PaginationMeta,
    ErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Константы пагинации
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def get_session() -> Session:
    """Получение сессии БД"""
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
    """
    Получение списка стажировок с фильтрацией и пагинацией
    
    **Параметры:**
    - `page`: Номер страницы (по умолчанию 1)
    - `city`: Список городов для фильтрации (например: city=Москва&city=Санкт-Петербург)
    - `format`: Список форматов работы (office, hybrid, remote)
    - `employment`: Список типов занятости (full-time, part-time)
    
    **Примеры:**
    - `/api/internship` - все стажировки, первая страница
    - `/api/internship?page=2` - вторая страница
    - `/api/internship?city=Москва&city=Санкт-Петербург` - в Москве и СПб
    - `/api/internship?format=hybrid&format=remote` - гибрид и удалённая работа
    """
    session = None
    try:
        session = get_session()
        
        # Построение базового запроса
        query = session.query(Internship)
        
        # Применение фильтров
        if city:
            query = query.filter(Internship.city.in_(city))
        
        if format:
            # Преобразование format код → значения БД
            format_mapping = {
                'office': 'Офис',
                'hybrid': 'Гибрид',
                'remote': 'Удалённая работа'
            }
            mapped_formats = [format_mapping.get(f, f) for f in format]
            query = query.filter(Internship.work_format.in_(mapped_formats))
        
        if employment:
            # employment пока не используется (можно добавить в модель)
            # Оставляем для совместимости с API
            pass
        
        # Получение общего количества записей
        total = query.count()
        
        # Пагинация
        page_size = DEFAULT_PAGE_SIZE
        skip = (page - 1) * page_size
        
        # Получение записей для текущей страницы
        internships = query.offset(skip).limit(page_size).all()
        
        # Преобразование в модели Pydantic
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
        
        # Расчет метаинформации
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
    """
    Получение полной информации о стажировке по UUID
    
    **Параметры:**
    - `internship_uuid`: UUID стажировки (например: 550e8400-e29b-41d4-a716-446655440000)
    
    **Ответ:**
    - Полная информация о стажировке или 404 ошибка если не найдена
    
    **Пример:**
    - `/api/internship/550e8400-e29b-41d4-a716-446655440000`
    """
    session = None
    try:
        session = get_session()
        
        # Поиск по UUID
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
