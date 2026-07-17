from __future__ import annotations

from fastapi import APIRouter, Request

from src.schemas.report import ReportListPage


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ReportListPage)
async def list_reports(request: Request, limit: int = 10, offset: int = 0):
    return await request.app.state.report_service.list_reports_page(
        limit=limit,
        offset=offset,
    )
