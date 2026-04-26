from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse


INGREDIENTS: List[str] = [
    "водка",
    "ром",
    "текила",
    "виски",
    "джин",
    "кола",
    "сок",
    "тоник",
    "лёд",
    "молоко",
]


MENU_DRINKS: List[Dict[str, Any]] = [
    {"name": "Куба Либре", "price": 15, "ingredients": ["кола", "лёд", "ром"]},
    {"name": "Отвёртка", "price": 12, "ingredients": ["водка", "сок"]},
    {"name": "Джин-тоник", "price": 14, "ingredients": ["джин", "лёд", "тоник"]},
    {"name": "Виски-кола", "price": 13, "ingredients": ["виски", "кола"]},
    {"name": "Текила-санрайз", "price": 14, "ingredients": ["сок", "текила"]},
    {"name": "Русский", "price": 10, "ingredients": ["водка", "лёд"]},
    {"name": "Белый русский", "price": 16, "ingredients": ["водка", "лёд", "молоко"]},
    {"name": "Лонг-Айленд", "price": 25, "ingredients": ["водка", "джин", "кола", "ром", "текила"]},
]

NIGHT_MENU_DRINKS: List[Dict[str, Any]] = [
    {"name": "Ночной русский", "price": 8, "ingredients": ["водка", "лёд", "молоко"]},
    {"name": "Бессонница", "price": 10, "ingredients": ["кола", "ром", "тоник"]},
    {"name": "Лунный свет", "price": 12, "ingredients": ["джин", "сок", "тоник"]},
]

MIX_RECIPES: Dict[Tuple[str, ...], Dict[str, Any]] = {
    tuple(sorted(["водка", "лёд"])): {"drink": "Русский", "price": 8},
    tuple(sorted(["водка", "сок"])): {"drink": "Отвёртка", "price": 10},
}


def _normalize_ingredients(items: List[str]) -> Tuple[str, ...]:
    return tuple(sorted(items))


def _mood_from_time(x_time: Optional[str]) -> str:
    if not x_time:
        return "normal"
    try:
        hh, mm = x_time.split(":", 1)
        h = int(hh)
        m = int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return "normal"
    except Exception:
        return "normal"
    if h >= 23 or h <= 5:
        return "grumpy"
    return "normal"


def _is_valid_time(x_time: Optional[str]) -> bool:
    if not x_time:
        return True
    try:
        hh, mm = x_time.split(":", 1)
        h = int(hh)
        m = int(mm)
        return 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        return False


@dataclass
class AccountState:
    id: str
    balance: int = 100
    orders: List[Dict[str, Any]] = field(default_factory=list)
    total_orders: int = 0
    unique_drinks: Set[str] = field(default_factory=set)

    def rank(self) -> str:
        return "Новичок" if self.total_orders == 0 else "Гость"


class OrderBody(BaseModel):
    name: str


class MixBody(BaseModel):
    ingredients: List[str]


class TipBody(BaseModel):
    amount: int = Field(ge=0)


app = FastAPI(title="Black Barmen API Clone", version="0.1.0")

_accounts_by_token: Dict[str, AccountState] = {}

@app.exception_handler(HTTPException)
async def http_exc_handler(_: Request, exc: HTTPException):
    # Match reference unauthorized shape (seen for /secret without auth).
    if exc.status_code == 401:
        return JSONResponse(
            status_code=401,
            content={"detail": {"status": "error", "error": "unauthorized"}},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def _new_id() -> str:
    while True:
        n = random.randint(10000, 99999)
        acc_id = f"BAR-{n}"
        if all(a.id != acc_id for a in _accounts_by_token.values()):
            return acc_id


def _new_token() -> str:
    return secrets.token_hex(24)


def _get_token_from_auth(auth: Optional[str]) -> str:
    if not auth:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


def _require_account(auth: Optional[str]) -> AccountState:
    token = _get_token_from_auth(auth)
    acc = _accounts_by_token.get(token)
    if acc is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return acc


@app.post("/register")
def register():
    acc_id = _new_id()
    token = _new_token()
    _accounts_by_token[token] = AccountState(id=acc_id)
    return {"status": "ok", "id": acc_id, "token": token}


@app.post("/reset")
def reset(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    acc = _require_account(authorization)
    _accounts_by_token[_get_token_from_auth(authorization)] = AccountState(id=acc.id)
    return {"status": "ok"}


@app.get("/menu")
def menu(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_time: Optional[str] = Header(default=None, alias="X-Time"),
):
    acc = _require_account(authorization)
    drinks = MENU_DRINKS if _is_valid_time(x_time) else NIGHT_MENU_DRINKS
    return {
        "status": "ok",
        "drinks": drinks,
        "balance": acc.balance,
        "mood_level": "normal",
    }


@app.post("/order")
def order(
    body: OrderBody,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_time: Optional[str] = Header(default=None, alias="X-Time"),
):
    acc = _require_account(authorization)
    mood = _mood_from_time(x_time)

    drink = next((d for d in MENU_DRINKS if d["name"] == body.name), None)
    if drink is None:
        return {"status": "error", "error": "unknown_drink", "balance": acc.balance, "mood_level": mood}

    price = int(drink["price"])
    if acc.balance < price:
        return {
            "status": "error",
            "error": "insufficient_funds",
            "price": price,
            "balance": acc.balance,
            "mood_level": mood,
        }

    acc.balance -= price
    acc.orders.append({"drink": drink["name"], "price": price, "method": "order"})
    acc.total_orders += 1
    acc.unique_drinks.add(drink["name"])
    return {
        "status": "ok",
        "drink": drink["name"],
        "price": price,
        "balance": acc.balance,
        "mood_level": mood,
    }


@app.post("/mix")
def mix(
    body: MixBody,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_time: Optional[str] = Header(default=None, alias="X-Time"),
):
    acc = _require_account(authorization)
    mood = _mood_from_time(x_time)

    key = _normalize_ingredients(body.ingredients)
    recipe = MIX_RECIPES.get(key)
    if recipe is None:
        return {"status": "error", "error": "unknown_recipe", "balance": acc.balance, "mood_level": mood}

    price = int(recipe["price"])
    if acc.balance < price:
        return {
            "status": "error",
            "error": "insufficient_funds",
            "price": price,
            "balance": acc.balance,
            "mood_level": mood,
        }

    acc.balance -= price
    acc.orders.append({"drink": recipe["drink"], "price": price, "method": "mix"})
    acc.total_orders += 1
    acc.unique_drinks.add(recipe["drink"])
    return {
        "status": "ok",
        "drink": recipe["drink"],
        "price": price,
        "balance": acc.balance,
        "mood_level": mood,
    }


@app.get("/balance")
def balance(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    acc = _require_account(authorization)
    return {"status": "ok", "balance": acc.balance, "mood_level": "normal"}


@app.post("/tip")
def tip(body: TipBody, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    acc = _require_account(authorization)
    amount = int(body.amount)
    if acc.balance < amount:
        return {"status": "error", "error": "insufficient_funds", "balance": acc.balance, "mood_level": "normal"}
    acc.balance -= amount
    return {"status": "ok", "tip": amount, "balance": acc.balance, "mood_level": "normal"}


@app.get("/history")
def history(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    acc = _require_account(authorization)
    return {
        "status": "ok",
        "orders": acc.orders,
        "balance": acc.balance,
        "mood_level": "normal",
    }


@app.get("/profile")
def profile(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    acc = _require_account(authorization)
    return {
        "status": "ok",
        "id": acc.id,
        "rank": acc.rank(),
        "total_orders": acc.total_orders,
        "unique_drinks": len(acc.unique_drinks),
        "favorite_drink": None,
        "bar_closed": False,
    }


@app.get("/ingredients")
def ingredients(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    acc = _require_account(authorization)
    return {"status": "ok", "ingredients": INGREDIENTS, "balance": acc.balance, "mood_level": "normal"}


@app.get("/secret")
def secret(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    _ = _require_account(authorization)
    return {"status": "error", "error": "not_found"}

