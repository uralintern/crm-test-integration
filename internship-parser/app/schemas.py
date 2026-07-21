"""
Pydantic модели для API ответов
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class InternshipBase(BaseModel):
    """Базовая модель стажировки"""
    title: str = Field(..., description="Название должности")
    direction: str = Field(..., description="Направление работы")
    company: str = Field(..., description="Название компании")
    city: Optional[str] = Field(None, description="Город")
    work_format: Optional[str] = Field(None, description="Формат работы")
    link: str = Field(..., description="Ссылка на вакансию")
    salary_from: Optional[int] = Field(None, description="Начальная зарплата")
    description: Optional[str] = Field(None, description="Описание стажировки")


class InternshipDetail(InternshipBase):
    """Полная информация о стажировке"""
    id: UUID = Field(..., description="UUID стажировки")
    
    class Config:
        from_attributes = True


class InternshipListItem(InternshipBase):
    """Элемент в списке стажировок"""
    id: UUID = Field(..., description="UUID стажировки")
    
    class Config:
        from_attributes = True


class PaginationMeta(BaseModel):
    """Метаинформация о пагинации"""
    total: int = Field(..., description="Общее количество записей")
    page: int = Field(..., description="Текущая страница")
    page_size: int = Field(..., description="Размер страницы")
    total_pages: int = Field(..., description="Общее количество страниц")


class InternshipsListResponse(BaseModel):
    """Ответ со списком стажировок"""
    data: list[InternshipListItem] = Field(..., description="Список стажировок")
    pagination: PaginationMeta = Field(..., description="Метаинформация о пагинации")
    
    class Config:
        json_schema_extra = {
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
                        "description": "Разработка бэкенда на Python"
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


class InternshipDetailResponse(InternshipDetail):
    """Ответ с полной информацией о стажировке"""
    
    class Config:
        from_attributes = True
        json_schema_extra = {
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


class ErrorResponse(BaseModel):
    """Ошибка в ответе"""
    detail: str = Field(..., description="Описание ошибки")
    status_code: int = Field(..., description="HTTP статус код")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Стажировка не найдена",
                "status_code": 404
            }
        }
