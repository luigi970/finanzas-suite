from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter()

class ProfileIn(BaseModel):
    cuit: str
    razon_social: Optional[str] = None
    condicion: Optional[str] = None          # monotributo|responsable_inscripto|relacion_dependencia|otro
    categoria_monotributo: Optional[str] = None  # A-K
    tiene_inmuebles: Optional[int] = 0
    tiene_vehiculos: Optional[int] = 0
    tiene_inversiones: Optional[int] = 0
    opera_cripto: Optional[int] = 0
    opera_cedears: Optional[int] = 0
    usa_broker: Optional[int] = 0
    tiene_caja_ahorro_usd: Optional[int] = 0
    periodo_fiscal: Optional[str] = None
    notas: Optional[str] = None

@router.get("/api/profile")
def get_profile():
    db = get_db()
    row = db.execute("SELECT * FROM fiscal_profile ORDER BY id LIMIT 1").fetchone()
    db.close()
    return dict(row) if row else {}

@router.post("/api/profile")
def save_profile(data: ProfileIn):
    db = get_db()
    existing = db.execute("SELECT id FROM fiscal_profile LIMIT 1").fetchone()
    if existing:
        db.execute("""
            UPDATE fiscal_profile SET
                cuit=?, razon_social=?, condicion=?, categoria_monotributo=?,
                tiene_inmuebles=?, tiene_vehiculos=?, tiene_inversiones=?,
                opera_cripto=?, opera_cedears=?, usa_broker=?, tiene_caja_ahorro_usd=?,
                periodo_fiscal=?, notas=?, updated_at=datetime('now')
            WHERE id=?
        """, (data.cuit, data.razon_social, data.condicion, data.categoria_monotributo,
              data.tiene_inmuebles, data.tiene_vehiculos, data.tiene_inversiones,
              data.opera_cripto, data.opera_cedears, data.usa_broker, data.tiene_caja_ahorro_usd,
              data.periodo_fiscal, data.notas, existing["id"]))
    else:
        db.execute("""
            INSERT INTO fiscal_profile
                (cuit, razon_social, condicion, categoria_monotributo,
                 tiene_inmuebles, tiene_vehiculos, tiene_inversiones,
                 opera_cripto, opera_cedears, usa_broker, tiene_caja_ahorro_usd,
                 periodo_fiscal, notas)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (data.cuit, data.razon_social, data.condicion, data.categoria_monotributo,
              data.tiene_inmuebles, data.tiene_vehiculos, data.tiene_inversiones,
              data.opera_cripto, data.opera_cedears, data.usa_broker, data.tiene_caja_ahorro_usd,
              data.periodo_fiscal, data.notas))
    db.commit()
    db.close()
    return {"ok": True}
