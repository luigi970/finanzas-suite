def build_prompt(s: dict) -> str:
    raw = s.get("ticker", "?")
    ticker = raw[:-4] if raw.endswith("-USD") else raw
    price  = s.get("price") or 0

    signal_label = {
        "compra_fuerte": "COMPRA FUERTE",
        "compra":        "COMPRA",
        "neutral":       "NEUTRAL",
        "venta":         "VENTA",
        "venta_fuerte":  "VENTA FUERTE",
    }.get(s.get("signal", "neutral"), "NEUTRAL")

    direction = s.get("direction", "NEUTRAL")

    zone_desc = {
        "discount": "zona de descuento (precio bajo respecto a su historia reciente)",
        "fair":     "zona de valor justo (precio equilibrado)",
        "premium":  "zona premium (precio elevado respecto a su historia reciente)",
    }.get(s.get("zone", "fair"), "zona de valor justo")

    # ── Medias móviles ───────────────────────────────────────────────────────
    ma_parts = []
    for name, key in [
        ("MA5",  "pct_vs_ma5"),  ("MA10", "pct_vs_ma10"), ("MA20", "pct_vs_ma20"),
        ("MA50", "pct_vs_ma50"), ("MA200","pct_vs_ma200"),
    ]:
        v = s.get(key)
        if v is not None:
            ma_parts.append(f"{name}: {'+' if v >= 0 else ''}{v:.1f}%")
    ma_line = " | ".join(ma_parts) if ma_parts else "no disponibles"

    # ── Indicadores contextualizados ─────────────────────────────────────────
    def _fmt(val): return str(round(val, 2)) if val is not None else "—"

    rsi   = s.get("rsi")
    rsi_note = (" — sobrecomprado, cuidado con una corrección" if rsi and rsi > 70 else
                " — sobrevendido, posible rebote" if rsi and rsi < 30 else
                " — zona neutral") if rsi else ""

    adx   = s.get("adx")
    adx_note = (" — tendencia definida y fuerte" if adx and adx > 25 else
                " — sin tendencia clara, mercado lateral" if adx and adx < 15 else
                " — tendencia moderada") if adx else ""

    macd  = s.get("macd_hist")
    macd_note = (" — momentum alcista" if macd and macd > 0 else
                 " — momentum bajista") if macd is not None else ""

    pct_b = s.get("pct_b")
    bb_note = (" — precio tocando el techo de la banda, presión vendedora probable" if pct_b and pct_b > 0.8 else
               " — precio en el piso de la banda, zona de soporte técnico"           if pct_b and pct_b < 0.2 else
               "") if pct_b is not None else ""

    vol   = s.get("vol_ratio")
    vol_note = (" — volumen excepcionalmente alto, hay interés institucional real" if vol and vol > 2.0 else
                " — volumen por encima del promedio, señal de convicción"           if vol and vol > 1.5 else
                " — volumen por debajo del promedio, movimiento sin convicción"     if vol and vol < 0.7 else
                "") if vol else ""

    # ── Patrón de velas ──────────────────────────────────────────────────────
    candle = s.get("candle_pattern")
    candle_txt = "sin patrón especial en las últimas velas"
    if candle and isinstance(candle, dict) and candle.get("name"):
        type_map = {"bullish": "señal alcista", "bearish": "señal bajista", "neutral": "señal de indecisión"}
        tipo = type_map.get(candle.get("type", ""), "")
        candle_txt = f"{candle['name']}{' (' + tipo + ')' if tipo else ''}"

    # ── Helper Pulse ─────────────────────────────────────────────────────────
    pulse_parts = [p for p in [s.get("pulse_state"), s.get("pulse_signal")] if p]
    pulse_txt   = " / ".join(pulse_parts) if pulse_parts else "NEUTRAL"

    # ── Pivots (solo S1, P, R1 para no sobrecargar) ──────────────────────────
    pivots_line = ""
    pivots  = s.get("pivots") or {}
    classic = pivots.get("classic") or {}
    if classic:
        P, R1, S1 = classic.get("P"), classic.get("R1"), classic.get("S1")
        if P and R1 and S1:
            pos = "por encima del pivot" if price > P else "por debajo del pivot"
            pivots_line = (
                f"\nNiveles pivot del día: Soporte S1=${S1} | Pivot central P=${P} ({pos}) | Resistencia R1=${R1}"
            )

    # ── Prompt final ─────────────────────────────────────────────────────────
    system = (
        "Sos el mejor analista financiero del mundo. "
        "Combinás la precisión de un quant con la calidez de un gran comunicador. "
        "Tu misión es explicarle a una persona común — sin experiencia en mercados — "
        "qué conviene hacer con este activo hoy y por qué. "
        "Hablás como un amigo muy exitoso en inversiones: directo, confiado, sin jerga técnica. "
        "Cuando usás un término técnico, lo explicás en pocas palabras entre paréntesis. "
        "Escribís en español rioplatense. Sin bullets, sin títulos, sin markdown. "
        "El output es exactamente 4 o 5 oraciones seguidas, bien redactadas, que fluyan de forma natural."
    )

    data = (
        f"ACTIVO: {ticker} | Precio actual: ${price}\n"
        f"Señal del sistema: {signal_label} | Dirección dominante: {direction}\n"
        f"Puntaje alcista: {s.get('long_score', 0)}/100 | Puntaje bajista: {s.get('short_score', 0)}/100\n"
        "\n"
        f"Posición estructural: {zone_desc}\n"
        f"Distancia al máximo del año: {_fmt(s.get('pct_from_high'))}% | "
        f"Al mínimo del año: +{_fmt(s.get('pct_from_low'))}%\n"
        f"Precio de mayor volumen histórico (POC): ${_fmt(s.get('poc'))}\n"
        "\n"
        f"Medias móviles (precio vs promedio): {ma_line}\n"
        "\n"
        f"RSI (impulso): {_fmt(rsi)}{rsi_note}\n"
        f"MACD histograma: {_fmt(macd)}{macd_note}\n"
        f"Bollinger %B: {_fmt(pct_b)}{bb_note}\n"
        f"Momentum oscilador: {_fmt(s.get('mom'))} | Pulse: {pulse_txt}\n"
        f"ADX (fuerza de tendencia): {_fmt(adx)}{adx_note}\n"
        f"Volumen relativo al promedio: {_fmt(vol)}x{vol_note}\n"
        f"Patrón de velas reciente: {candle_txt}"
        f"{pivots_line}\n"
        "\n"
        f"Stop Loss sugerido: ${_fmt(s.get('sl'))} | TP1: ${_fmt(s.get('tp1'))} | TP2: ${_fmt(s.get('tp2'))}\n"
    )

    instruction = (
        "Escribí la recomendación empezando directamente con la conclusión (qué conviene hacer, sin rodeos). "
        "Usá los 2 o 3 datos más relevantes de forma natural dentro del texto, sin listarlos. "
        "Indicá brevemente dónde estaría la señal de que la idea falla. "
        "Terminá con una frase que dé perspectiva sobre el riesgo o la oportunidad. "
        "Soná como un experto de verdad hablando con un amigo, no como un reporte automático.\n\n"
        "Recomendación:"
    )

    return f"{system}\n\n{data}\n{instruction}"
