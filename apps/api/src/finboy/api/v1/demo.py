from fastapi import APIRouter

from finboy.services.money.http import MoneyRoute
from finboy.services.ux.contracts import DemoView
from finboy.services.ux.demo import demo_view

router = APIRouter(tags=["demo"], route_class=MoneyRoute)


@router.get("/demo", response_model=DemoView)
def demo() -> dict:
    return demo_view()
