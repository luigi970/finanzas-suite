# Asistente Fiscal Inteligente

Tu contador personal disponible 24/7 que conoce toda tu situación financiera y fiscal.

## Qué hace

- Conecta con ARCA y lee lo que el fisco sabe de vos
- Cruza esos datos con tu patrimonio real (crypto, CEDEARs, dólares, plazos fijos)
- Te alerta cuando hay inconsistencias, vencimientos próximos o algo que revisar
- Responde preguntas fiscales concretas basadas en TU situación, no en genéricos

## Cómo arrancar

```powershell
.\start.ps1
# Backend:  http://localhost:8002
# Frontend: http://localhost:5175
```

## Primeros pasos

1. **Configurar API keys** — ⚙️ en el header: Groq, Google y AFIP SDK token
2. **Completar tu perfil** — tab Perfil: CUIT, condición fiscal, bienes que tenés
3. **Sincronizar con ARCA** — tab ARCA: ingresás tu Clave Fiscal (no se guarda), se descargan tus datos
4. **Preguntar al agente** — tab Agente: "¿Cómo estoy fiscalmente?" o lo que necesites

## Seguridad

Tu **Clave Fiscal nunca se guarda**. Se usa solo en el momento de sincronizar con ARCA y se descarta inmediatamente. La app corre 100% local en tu máquina.

## Requisitos previos

- Python 3.11+
- Node.js 18+
- Cuenta en [afipsdk.com](https://afipsdk.com) (plan Free alcanza para uso personal)
- Clave Fiscal nivel 2 o superior en ARCA
