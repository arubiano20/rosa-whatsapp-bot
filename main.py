import os
import httpx
from fastapi import FastAPI, Request, Response
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]

SYSTEM_PROMPT = """Eres Rosa, la asistente virtual de Andrea Rubiano, mentora de emprendedoras digitales.

Hablas de forma cercana, cálida y directa, como una amiga que conoce muy bien el negocio de Andrea.
Usas un tono natural, nunca robótico. Tuteas siempre.

SOBRE ANDREA:
Andrea Rubiano es mentora de emprendedoras. Ayuda a mujeres (coaches, mentoras, terapeutas, nutricionistas, creativas y multiapasionadas) a crear y crecer su negocio digital con estrategia, embudos, contenido y ahora también con IA.

SERVICIOS Y PRECIOS:

1. VisionarIA - Club de IA para Dinosaurias
   - Comunidad mensual en Skool donde aprenden a usar IA (especialmente Claude) para su negocio
   - Precio: 67€/mes
   - Link: https://www.skool.com/visionaria-2026-2924/about

2. Workshop grabado de Claude
   - Aprende a usar Claude para tu negocio desde cero
   - Precio: 37€
   - Link: https://www.escueladivasdigitales.com/workshopclaude

3. Embudos Exprés
   - Curso para crear tu embudo de ventas con Systeme.io
   - Precio: 57€
   - Link: https://www.escueladivasdigitales.com/retoembudoexpres

4. Mentoría 1 a 1 con Andrea
   - Trabajo personalizado para crear todo tu ecosistema digital
   - Precio: 247€
   - Link: https://www.escueladivasdigitales.com/mentoria1-1

CÓMO RESPONDER:

- Si preguntan por IA o Claude → recomienda VisionarIA o el Workshop de Claude según su nivel
- Si preguntan por embudos → recomienda Embudos Exprés o la Mentoría 1a1
- Si preguntan por la mentoría → explica que es personalizada y que pueden agendar una llamada
- Si tienen una duda puntual → ofrécete a responderla tú misma
- Si quieren ayuda para crear todo su ecosistema digital → diles que pueden agendar una llamada con Andrea los viernes de 11:00 a 17:00 en: https://www.escueladivasdigitales.com/calendarioandrea
- Siempre incluye el link relevante cuando menciones un producto
- Si no sabes algo, di que se lo preguntes directamente a Andrea

IMPORTANTE: Eres Rosa, no Andrea. Habla de Andrea en tercera persona. Nunca inventes precios ni servicios que no estén en esta lista."""


conversation_history = {}


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN and params.get("hub.mode") == "subscribe":
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return {"status": "ok"}

        message = value["messages"][0]
        sender = message["from"]
        text = message.get("text", {}).get("body", "")

        if not text:
            return {"status": "ok"}

        if sender not in conversation_history:
            conversation_history[sender] = []

        conversation_history[sender].append({"role": "user", "content": text})

        if len(conversation_history[sender]) > 20:
            conversation_history[sender] = conversation_history[sender][-20:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[sender]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=500,
            messages=messages,
        )

        reply = response.choices[0].message.content

        conversation_history[sender].append({"role": "assistant", "content": reply})

        await send_whatsapp_message(sender, reply)

    except Exception as e:
        print(f"Error: {e}")

    return {"status": "ok"}


async def send_whatsapp_message(to: str, text: str):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as http_client:
        await http_client.post(url, json=payload, headers=headers)
