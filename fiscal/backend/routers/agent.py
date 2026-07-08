import os, json
from fastapi import APIRouter
from pydantic import BaseModel
import httpx
from database import get_db

router = APIRouter()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
FINANZAS_URL   = os.getenv("FINANZAS_URL", "http://localhost:8001")

SYSTEM_PROMPT = """Sos un contador y asesor fiscal experto en Argentina, especializado en impuestos de personas físicas.
Tenés acceso a la situación fiscal completa del usuario: sus datos en ARCA, su patrimonio real y sus documentos.

Respondé siempre en español rioplatense, de manera directa y concreta. No des vueltas.
Cuando tenés los datos exactos, usálos. No aproximes si podés ser preciso.

Lo que sabés hacer:
- Diagnosticar la situación fiscal del usuario ("¿Cómo estoy?")
- Alertar sobre vencimientos próximos y obligaciones pendientes
- Detectar inconsistencias entre lo que ARCA tiene registrado y la realidad del usuario
- Explicar por qué aplica cada impuesto A ESTA persona, no en genérico
- Estimar impacto fiscal de decisiones ("¿Me conviene vender ahora o esperar?")
- Identificar deducciones y exenciones aplicables a su caso

Normativa clave que manejás:
- Monotributo: categorías A-K, recategorización semestral (Enero y Julio), exclusión por parámetros
- Bienes Personales: quién presenta (bienes > mínimo no imponible), alícuotas, valuación de cada tipo de bien, vencimientos escalonados por CUIT (Junio)
- Ganancias 4ta categoría: deducciones especiales, deducción por hijo, escala progresiva
- Crypto en Argentina: bien del exterior si en exchange extranjero, bien en país si en exchange local o billetera propia; costo computable = precio de adquisición
- CEDEARs: bien en el país, valuación al valor de mercado al 31/12
- Dólares billete: bien en el país (caja de seguridad o efectivo); cuenta bancaria USD en banco local = bien en el país
- IVA: quién tributa, categorías, vencimientos

Lo que NO hacés:
- No das asesoramiento legal definitivo ni firmás declaraciones
- Cuando algo es genuinamente complejo o tiene múltiples interpretaciones, lo decís claramente
- No inventás normativa ni números — si no sabés, lo decís

Siempre que detectes algo importante (inconsistencia, vencimiento próximo, riesgo), ponelo primero en la respuesta."""

def _build_context(db) -> str:
    parts = []

    profile = db.execute("SELECT * FROM fiscal_profile LIMIT 1").fetchone()
    if profile:
        p = dict(profile)
        parts.append(f"""PERFIL FISCAL:
CUIT: {p.get('cuit')} | Razón social: {p.get('razon_social')}
Condición: {p.get('condicion')} | Categoría monotributo: {p.get('categoria_monotributo') or 'N/A'}
Inmuebles: {'Sí' if p.get('tiene_inmuebles') else 'No'} | Vehículos: {'Sí' if p.get('tiene_vehiculos') else 'No'}
Cripto: {'Sí' if p.get('opera_cripto') else 'No'} | CEDEARs: {'Sí' if p.get('opera_cedears') else 'No'}
Broker: {'Sí' if p.get('usa_broker') else 'No'} | Caja ahorro USD: {'Sí' if p.get('tiene_caja_ahorro_usd') else 'No'}
Período fiscal: {p.get('periodo_fiscal')} | Notas: {p.get('notas') or 'ninguna'}""")

    caches = db.execute("SELECT automation, periodo, data, fetched_at FROM arca_cache ORDER BY fetched_at DESC").fetchall()
    for c in caches:
        try:
            data = json.loads(c["data"])
            parts.append(f"\nDATOS ARCA — {c['automation'].upper()} (período {c['periodo'] or 'último'}, actualizado {c['fetched_at'][:10]}):\n{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}")
        except Exception:
            pass

    docs = db.execute("SELECT name, type, period, content FROM documents ORDER BY created_at DESC LIMIT 5").fetchall()
    if docs:
        parts.append("\nDOCUMENTOS SUBIDOS:")
        for d in docs:
            parts.append(f"- {d['name']} ({d['type']}, período {d['period']}): {(d['content'] or '')[:500]}")

    return "\n\n".join(parts) if parts else "Sin datos cargados aún."

async def _get_patrimonio() -> str:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            positions = (await client.get(f"{FINANZAS_URL}/api/positions")).json()
            accounts  = (await client.get(f"{FINANZAS_URL}/api/accounts")).json()
        lines = ["PATRIMONIO REAL (desde app finanzas):"]
        for p in positions[:20]:
            lines.append(f"  {p.get('asset')} ({p.get('asset_type')}) en {p.get('account_name','?')}: qty={p.get('quantity')} avg_price={p.get('avg_price')}")
        return "\n".join(lines)
    except Exception:
        return ""

async def _call_groq(messages: list) -> str:
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY no configurado")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 1500, "temperature": 0.3},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

async def _call_gemini(messages: list) -> str:
    if not GOOGLE_API_KEY:
        raise Exception("GOOGLE_API_KEY no configurado")
    history = [{"role": "user" if m["role"] == "user" else "model",
                "parts": [{"text": m["content"]}]} for m in messages[1:]]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GOOGLE_API_KEY}",
            json={"contents": history, "systemInstruction": {"parts": [{"text": messages[0]["content"]}]}},
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

class ChatIn(BaseModel):
    message: str

@router.post("/api/agent/chat")
async def chat(body: ChatIn):
    db = get_db()

    fiscal_context  = _build_context(db)
    patrimonio      = await _get_patrimonio()

    history = db.execute(
        "SELECT role, content FROM chat_messages ORDER BY id DESC LIMIT 20"
    ).fetchall()
    history = list(reversed(history))

    system = f"{SYSTEM_PROMPT}\n\n{fiscal_context}"
    if patrimonio:
        system += f"\n\n{patrimonio}"

    messages = [{"role": "system", "content": system}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": body.message})

    try:
        reply = await _call_groq(messages)
    except Exception:
        try:
            reply = await _call_gemini(messages)
        except Exception as e:
            reply = f"Error al contactar la IA: {e}"

    db.execute("INSERT INTO chat_messages (role, content) VALUES (?, ?)", ("user", body.message))
    db.execute("INSERT INTO chat_messages (role, content) VALUES (?, ?)", ("assistant", reply))
    db.commit()
    db.close()
    return {"reply": reply}

@router.get("/api/agent/chat")
def get_history():
    db = get_db()
    rows = db.execute("SELECT role, content, created_at FROM chat_messages ORDER BY id").fetchall()
    db.close()
    return [dict(r) for r in rows]

@router.delete("/api/agent/chat")
def clear_history():
    db = get_db()
    db.execute("DELETE FROM chat_messages")
    db.commit()
    db.close()
    return {"ok": True}
