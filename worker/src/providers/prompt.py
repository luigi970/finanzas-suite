def build_prompt(s: dict) -> str:
    ticker = s.get("ticker", "?")
    signal = s.get("signal", "neutral")
    signal_label = {
        "compra_fuerte": "COMPRA FUERTE",
        "compra": "COMPRA",
        "neutral": "NEUTRAL",
        "venta": "VENTA",
        "venta_fuerte": "VENTA FUERTE",
    }.get(signal, signal.upper())

    return (
        f"Sos un analista técnico experto. Analizá el siguiente activo y escribí una "
        f"recomendación clara y concisa en español (máximo 4 oraciones). Sé directo, "
        f"usa datos concretos, no uses bullets ni markdown.\n\n"
        f"ACTIVO: {ticker}\n"
        f"Precio: {s.get('price')} | Señal: {signal_label} | Dirección: {s.get('direction', 'NEUTRAL')}\n"
        f"Score LONG: {s.get('long_score', 0)}/100 | Score SHORT: {s.get('short_score', 0)}/100\n"
        f"Zona estructural: {str(s.get('zone', 'fair')).upper()} | ADX: {s.get('adx')} | RSI: {s.get('rsi')}\n"
        f"Momentum oscilador: {s.get('mom')} | Pulse: {s.get('pulse_signal', 'NEUTRAL')} ({s.get('pulse_state', 'NEUTRAL')})\n"
        f"Volumen relativo: {s.get('vol_ratio')}x | %B Bollinger: {s.get('pct_b')}\n"
        f"Distancia de máximo 52s: {s.get('pct_from_high')}% | de mínimo: {s.get('pct_from_low')}%\n"
        f"vs MA200: {s.get('pct_vs_ma200')}% | POC volumen: {s.get('poc')}\n"
        f"MACD histograma: {s.get('macd_hist')}\n"
        f"SL sugerido: {s.get('sl')} | TP1 sugerido: {s.get('tp1')}\n\n"
        f"Recomendación:"
    )
