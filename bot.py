import logging
import asyncio
import os
import uuid
import time
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from tinydb import TinyDB, Query
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)

# --- CONFIGURAZIONE ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-1.5-flash")
FUSO_ITALIA = pytz.timezone("Europe/Rome")

# --- DATABASE ---
db = TinyDB("ricordino_db.json")
tabella_promemoria = db.table("promemoria")
tabella_stats = db.table("statistiche")
Q = Query()

logging.basicConfig(level=logging.INFO)

# --- STATI CONVERSAZIONE ---
(SCEGLI_AMICO, SCRIVI_PROMEMORIA, SCEGLI_TIPO_TEMPO,
 SCEGLI_UNITA, SCEGLI_QUANTITA, SCEGLI_ORA_PRECISA, SCEGLI_GIORNO) = range(7)

# --- AMICI ---
AMICI = {
    "sole": {"nome": "☀️ Sole", "descrizione": "Super positiva, ti carica sempre!", "fallback": "Ehi!! Ricordati di {cosa}!! Ce la fai!!"},
    "boh": {"nome": "🥱 Boh", "descrizione": "Se ne frega, ma ti ricorda lo stesso...", "fallback": "boh... {cosa}... fai te"},
    "giudice": {"nome": "⚖️ Il Giudice", "descrizione": "Sarcastico e spietato.", "fallback": "Ascolta. {cosa}. Fallo."},
    "mamma": {"nome": "👩 Mamma", "descrizione": "Drammatica, apprensiva, ti ama troppo.", "fallback": "Tesoro... {cosa}... mamma ci pensa..."},
}

PERSONALITA = {
    "sole": "Sei Sole, un'amica super positiva, calorosa ed entusiasta. Parli con energia esagerata, usi emoji solari e punti esclamativi.",
    "boh": "Sei Boh, un amico pigro e apatico. Parli in minuscolo, frasi corte, zero entusiasmo.",
    "giudice": "Sei Il Giudice, serio e sarcastico. Parli come un giudice di tribunale in modo ironico.",
    "mamma": "Sei Mamma, apprensiva e drammatica ma piena d'amore. Usi tanti puntini di sospensione e punti esclamativi.",
}

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# --- AI ---
async def genera_messaggio_ai(amico_key: str, cosa: str, tipo: str = "promemoria") -> str:
    if tipo == "conferma":
        istruzione = f"L'utente ha appena impostato un promemoria per: '{cosa}'. Scrivi UN SOLO messaggio brevissimo (max 2 righe) per confermare che hai ricevuto la richiesta e che lo ricorderai. Nel tuo tono caratteristico."
    else:
        istruzione = f"L'utente deve fare questa cosa: '{cosa}'. Scrivi UN SOLO messaggio di promemoria in italiano, massimo 3 righe. Non iniziare con 'Ciao'. Vai dritto al punto."
    try:
        risposta = await asyncio.to_thread(lambda: gemini.generate_content(f"{PERSONALITA[amico_key]}\n\n{istruzione}"))
        return risposta.text.strip()
    except Exception:
        return AMICI[amico_key]["fallback"].format(cosa=cosa)

# --- STATISTICHE ---
def aggiorna_stats(user_id: int, amico: str, completato: bool = None):
    stats = tabella_stats.get(Q.user_id == user_id)
    if not stats:
        stats = {"user_id": user_id, "totale": 0, "completati": 0, "non_completati": 0,
                 "per_amico": {"sole": 0, "boh": 0, "giudice": 0, "mamma": 0}, "streak": 0, "ultimo_completamento": 0}
        tabella_stats.insert(stats)
    if completato is True:
        tabella_stats.update({"completati": stats["completati"] + 1}, Q.user_id == user_id)
    elif completato is False:
        tabella_stats.update({"non_completati": stats["non_completati"] + 1}, Q.user_id == user_id)
    per_amico = stats["per_amico"]
    per_amico[amico] = per_amico.get(amico, 0) + 1
    tabella_stats.update({"totale": stats["totale"] + 1, "per_amico": per_amico}, Q.user_id == user_id)

# --- MANDA PROMEMORIA ---
async def manda_promemoria(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    suoneria = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suonerie", f"{data['amico']}.wav")
    if os.path.exists(suoneria):
        with open(suoneria, "rb") as f:
            await context.bot.send_voice(chat_id=data["chat_id"], voice=f)
    messaggio = await genera_messaggio_ai(data["amico"], data["cosa"])
    keyboard = [[
        InlineKeyboardButton("✅ Fatto!", callback_data=f"fatto_si_{data['job_id']}"),
        InlineKeyboardButton("❌ Non ancora", callback_data=f"fatto_no_{data['job_id']}"),
    ]]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=messaggio,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    if data.get("tipo") == "una_volta":
        tabella_promemoria.remove(Q.job_id == data["job_id"])
    aggiorna_stats(data["user_id"], data["amico"])

async def risposta_completamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    esito = parts[1]
    job_id = "_".join(parts[2:])
    user_id = query.from_user.id
    record = tabella_promemoria.get(Q.job_id == job_id)
    amico = record["amico"] if record else "sole"

    if esito == "si":
        aggiorna_stats(user_id, amico, completato=True)
        risposte = {
            "sole": "YAYYY!! Sapevo che ce la facevi!! Sei un mito!! ☀️🎉",
            "boh": "ah ok. bene. immagino.",
            "giudice": "Il Giudice prende atto. Sentenza: promossa/o. Può andare.",
            "mamma": "Amore mio!! Mamma è così felice!! Ti voglio bene!! 😭❤️",
        }
        await query.edit_message_reply_markup(None)
        await query.message.reply_text(risposte[amico])
    else:
        aggiorna_stats(user_id, amico, completato=False)
        risposte = {
            "sole": "Ehi, non ti preoccupare!! Ce la farai la prossima volta, credo in te!! ☀️",
            "boh": "vabbè. amen. ci riproviamo o no, fai te.",
            "giudice": "Peccato. Il Giudice è deluso ma non sorpreso. La prossima volta.",
            "mamma": "Tesoro... mamma capisce... però almeno ci hai provato, vero?? ❤️",
        }
        await query.edit_message_reply_markup(None)
        await query.message.reply_text(risposte[amico])

# --- RIPRISTINA AL RIAVVIO ---
async def ripristina_promemoria(app):
    ora = time.time()
    tutti = tabella_promemoria.all()
    ripristinati = 0
    for p in tutti:
        if p["tipo"] == "una_volta":
            secondi_rimasti = max(5, p["scatta_a"] - ora)
            app.job_queue.run_once(manda_promemoria, secondi_rimasti,
                data={"user_id": p["user_id"], "cosa": p["cosa"], "amico": p["amico"],
                      "chat_id": p["chat_id"], "job_id": p["job_id"], "tipo": "una_volta"},
                name=p["job_id"])
        elif p["tipo"] == "giornaliero":
            ora_parts = p["ora"].split(":")
            t = datetime.now(FUSO_ITALIA).replace(hour=int(ora_parts[0]), minute=int(ora_parts[1]), second=0, microsecond=0)
            app.job_queue.run_daily(manda_promemoria, t.timetz(),
                data={"user_id": p["user_id"], "cosa": p["cosa"], "amico": p["amico"],
                      "chat_id": p["chat_id"], "job_id": p["job_id"], "tipo": "giornaliero"},
                name=p["job_id"])
        elif p["tipo"] == "settimanale":
            ora_parts = p["ora"].split(":")
            t = datetime.now(FUSO_ITALIA).replace(hour=int(ora_parts[0]), minute=int(ora_parts[1]), second=0, microsecond=0)
            app.job_queue.run_daily(manda_promemoria, t.timetz(), days=(p["giorno"],),
                data={"user_id": p["user_id"], "cosa": p["cosa"], "amico": p["amico"],
                      "chat_id": p["chat_id"], "job_id": p["job_id"], "tipo": "settimanale"},
                name=p["job_id"])
        ripristinati += 1
    if ripristinati:
        print(f"Ripristinati {ripristinati} promemoria.")

# --- COMANDI BASE ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Ciao! Sono *Ricordino* — il promemoria che ti scrive come un amico vero!\n\n"
        "📌 /nuovo — aggiungi un promemoria\n"
        "📋 /lista — vedi i tuoi promemoria attivi\n"
        "🗑 /cancella — cancella un promemoria\n"
        "📊 /statistiche — le tue statistiche\n"
        "❓ /help — come funziona",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔔 *Come funziona Ricordino:*\n\n"
        "1️⃣ /nuovo → scegli l'amico\n"
        "2️⃣ Scrivi cosa devi fare\n"
        "3️⃣ Scegli quando: tra poco, orario preciso, ogni giorno o ogni settimana\n\n"
        "☀️ *Sole* — positiva, ti carica\n"
        "🥱 *Boh* — se ne frega ma ti ricorda\n"
        "⚖️ *Il Giudice* — sarcastico e spietato\n"
        "👩 *Mamma* — drammatica, ti ama troppo",
        parse_mode="Markdown"
    )

# --- NUOVO PROMEMORIA ---
async def nuovo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("☀️ Sole", callback_data="sole"),
         InlineKeyboardButton("🥱 Boh", callback_data="boh")],
        [InlineKeyboardButton("⚖️ Il Giudice", callback_data="giudice"),
         InlineKeyboardButton("👩 Mamma", callback_data="mamma")],
    ]
    await update.message.reply_text("Chi vuoi che ti ricordi la cosa?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SCEGLI_AMICO

async def scegli_amico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["amico"] = query.data
    info = AMICI[query.data]
    await query.edit_message_text(
        f"Hai scelto *{info['nome']}* — {info['descrizione']}\n\nCosa devo ricordarti?",
        parse_mode="Markdown"
    )
    return SCRIVI_PROMEMORIA

async def scrivi_promemoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cosa"] = update.message.text
    keyboard = [
        [InlineKeyboardButton("⏱ Tra poco", callback_data="tipo_trapoco"),
         InlineKeyboardButton("🕐 Orario preciso", callback_data="tipo_orario")],
        [InlineKeyboardButton("📅 Ogni giorno", callback_data="tipo_giornaliero"),
         InlineKeyboardButton("📆 Ogni settimana", callback_data="tipo_settimanale")],
    ]
    await update.message.reply_text(
        f"Annotato: *{update.message.text}*\n\nQuando vuoi che ti ricordi?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SCEGLI_TIPO_TEMPO

async def scegli_tipo_tempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipo = query.data
    context.user_data["tipo"] = tipo

    if tipo == "tipo_trapoco":
        keyboard = [
            [InlineKeyboardButton("⏱ Minuti", callback_data="unita_minuti"),
             InlineKeyboardButton("🕐 Ore", callback_data="unita_ore")],
        ]
        await query.edit_message_text("In minuti o in ore?", reply_markup=InlineKeyboardMarkup(keyboard))
        return SCEGLI_UNITA

    elif tipo == "tipo_orario":
        await query.edit_message_text("A che ora? Scrivila così: *18:30*", parse_mode="Markdown")
        return SCEGLI_ORA_PRECISA

    elif tipo == "tipo_giornaliero":
        await query.edit_message_text("A che ora ogni giorno? Scrivila così: *09:00*", parse_mode="Markdown")
        return SCEGLI_ORA_PRECISA

    elif tipo == "tipo_settimanale":
        keyboard = [[InlineKeyboardButton(g, callback_data=f"giorno_{i}")] for i, g in enumerate(GIORNI)]
        await query.edit_message_text("Che giorno della settimana?", reply_markup=InlineKeyboardMarkup(keyboard))
        return SCEGLI_GIORNO

async def scegli_unita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["unita"] = query.data.replace("unita_", "")
    if context.user_data["unita"] == "minuti":
        keyboard = [
            [InlineKeyboardButton("5 min", callback_data="q_5"),
             InlineKeyboardButton("10 min", callback_data="q_10"),
             InlineKeyboardButton("15 min", callback_data="q_15")],
            [InlineKeyboardButton("20 min", callback_data="q_20"),
             InlineKeyboardButton("30 min", callback_data="q_30"),
             InlineKeyboardButton("45 min", callback_data="q_45")],
            [InlineKeyboardButton("✏️ Scrivi tu", callback_data="q_custom")],
        ]
        await query.edit_message_text("Fra quanti minuti?", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard = [
            [InlineKeyboardButton("1 ora", callback_data="q_60"),
             InlineKeyboardButton("2 ore", callback_data="q_120"),
             InlineKeyboardButton("3 ore", callback_data="q_180")],
            [InlineKeyboardButton("6 ore", callback_data="q_360"),
             InlineKeyboardButton("12 ore", callback_data="q_720"),
             InlineKeyboardButton("24 ore", callback_data="q_1440")],
            [InlineKeyboardButton("✏️ Scrivi tu", callback_data="q_custom")],
        ]
        await query.edit_message_text("Fra quante ore?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SCEGLI_QUANTITA

async def scegli_quantita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "q_custom":
        unita = context.user_data.get("unita", "minuti")
        await query.edit_message_text(f"Scrivi quanti {'minuti' if unita == 'minuti' else 'ore'}:")
        return SCEGLI_QUANTITA
    minuti = int(query.data.replace("q_", ""))
    secondi = minuti * 60
    unita = context.user_data.get("unita", "minuti")
    etichetta = f"{minuti} minuti" if unita == "minuti" else f"{minuti // 60} ora/e"
    await programma_una_volta(update, context, secondi, etichetta, query=query)
    return ConversationHandler.END

async def scegli_quantita_testo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valore = float(update.message.text.replace(",", "."))
        if valore <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Scrivi un numero valido, es. 10 o 30")
        return SCEGLI_QUANTITA
    unita = context.user_data.get("unita", "minuti")
    secondi = int(valore * 60) if unita == "minuti" else int(valore * 3600)
    etichetta = f"{valore:.0f} {'minuti' if unita == 'minuti' else 'ora/e'}"
    await programma_una_volta(update, context, secondi, etichetta)
    return ConversationHandler.END

async def scegli_ora_precisa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = update.message.text.strip()
    try:
        ora_parts = testo.split(":")
        if len(ora_parts) != 2:
            raise ValueError
        h, m = int(ora_parts[0]), int(ora_parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Formato non valido. Scrivi così: *18:30*", parse_mode="Markdown")
        return SCEGLI_ORA_PRECISA

    tipo = context.user_data.get("tipo")
    amico = context.user_data["amico"]
    cosa = context.user_data["cosa"]
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    job_id = str(uuid.uuid4())

    if tipo == "tipo_orario":
        # Una volta all'orario preciso
        ora_it = datetime.now(FUSO_ITALIA).replace(hour=h, minute=m, second=0, microsecond=0)
        if ora_it <= datetime.now(FUSO_ITALIA):
            ora_it += timedelta(days=1)
        secondi = (ora_it - datetime.now(FUSO_ITALIA)).total_seconds()
        etichetta = f"alle {testo}"
        await programma_una_volta(update, context, int(secondi), etichetta, job_id=job_id)

    elif tipo == "tipo_giornaliero":
        ora_t = datetime.now(FUSO_ITALIA).replace(hour=h, minute=m, second=0, microsecond=0).timetz()
        tabella_promemoria.insert({"job_id": job_id, "user_id": user_id, "chat_id": chat_id,
            "amico": amico, "cosa": cosa, "tipo": "giornaliero", "ora": testo, "etichetta": f"ogni giorno alle {testo}"})
        context.application.job_queue.run_daily(manda_promemoria, ora_t,
            data={"user_id": user_id, "cosa": cosa, "amico": amico, "chat_id": chat_id, "job_id": job_id, "tipo": "giornaliero"},
            name=job_id)
        conferma = await genera_messaggio_ai(amico, cosa, tipo="conferma")
        await update.message.reply_text(f"{AMICI[amico]['nome']} — ogni giorno alle {testo}\n\n{conferma}")

    elif tipo == "tipo_settimanale":
        giorno_idx = context.user_data.get("giorno_idx", 0)
        giorno_nome = GIORNI[giorno_idx]
        ora_t = datetime.now(FUSO_ITALIA).replace(hour=h, minute=m, second=0, microsecond=0).timetz()
        tabella_promemoria.insert({"job_id": job_id, "user_id": user_id, "chat_id": chat_id,
            "amico": amico, "cosa": cosa, "tipo": "settimanale", "ora": testo, "giorno": giorno_idx,
            "etichetta": f"ogni {giorno_nome} alle {testo}"})
        context.application.job_queue.run_daily(manda_promemoria, ora_t, days=(giorno_idx,),
            data={"user_id": user_id, "cosa": cosa, "amico": amico, "chat_id": chat_id, "job_id": job_id, "tipo": "settimanale"},
            name=job_id)
        conferma = await genera_messaggio_ai(amico, cosa, tipo="conferma")
        await update.message.reply_text(f"{AMICI[amico]['nome']} — ogni {giorno_nome} alle {testo}\n\n{conferma}")

    return ConversationHandler.END

async def scegli_giorno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    giorno_idx = int(query.data.replace("giorno_", ""))
    context.user_data["giorno_idx"] = giorno_idx
    await query.edit_message_text(f"Ogni *{GIORNI[giorno_idx]}* a che ora? Scrivila così: *18:30*", parse_mode="Markdown")
    return SCEGLI_ORA_PRECISA

async def programma_una_volta(update, context, secondi, etichetta, query=None, job_id=None):
    if job_id is None:
        job_id = str(uuid.uuid4())
    amico = context.user_data["amico"]
    cosa = context.user_data["cosa"]
    if query:
        user_id = query.from_user.id
        chat_id = query.message.chat_id
    else:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id

    tabella_promemoria.insert({"job_id": job_id, "user_id": user_id, "chat_id": chat_id,
        "amico": amico, "cosa": cosa, "tipo": "una_volta", "scatta_a": time.time() + secondi, "etichetta": etichetta})

    context.application.job_queue.run_once(manda_promemoria, secondi,
        data={"user_id": user_id, "cosa": cosa, "amico": amico, "chat_id": chat_id, "job_id": job_id, "tipo": "una_volta"},
        name=job_id)

    conferma = await genera_messaggio_ai(amico, cosa, tipo="conferma")
    testo = f"{AMICI[amico]['nome']} — {etichetta}\n\n{conferma}"
    if query:
        await query.edit_message_text(testo)
    else:
        await update.message.reply_text(testo)

# --- LISTA ---
async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    items = tabella_promemoria.search(Q.user_id == user_id)
    if not items:
        await update.message.reply_text("Non hai promemoria attivi! Scrivi /nuovo per aggiungerne uno.")
        return
    testo = "📋 *I tuoi promemoria attivi:*\n\n"
    for i, p in enumerate(items, 1):
        if p["tipo"] == "una_volta":
            rimasti = max(0, int(p["scatta_a"] - time.time()))
            ore = rimasti // 3600
            minuti = (rimasti % 3600) // 60
            secondi = rimasti % 60
            if ore > 0:
                tempo = f"tra {ore}h {minuti}m"
            elif minuti > 0:
                tempo = f"tra {minuti}m {secondi}s"
            else:
                tempo = f"tra {secondi}s"
        else:
            tempo = p.get("etichetta", "ricorrente")
        testo += f"{i}. _{p['cosa']}_ — {AMICI[p['amico']]['nome']} — *{tempo}*\n"
    await update.message.reply_text(testo, parse_mode="Markdown")

# --- CANCELLA ---
async def cancella(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    items = tabella_promemoria.search(Q.user_id == user_id)
    if not items:
        await update.message.reply_text("Non hai promemoria attivi da cancellare.")
        return
    keyboard = [[InlineKeyboardButton(f"❌ {p['cosa'][:30]} — {AMICI[p['amico']]['nome']}", callback_data=f"del_{p['job_id']}")] for p in items]
    await update.message.reply_text("Quale vuoi cancellare?", reply_markup=InlineKeyboardMarkup(keyboard))

async def conferma_cancella(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    job_id = query.data.replace("del_", "")
    tabella_promemoria.remove(Q.job_id == job_id)
    for job in context.application.job_queue.get_jobs_by_name(job_id):
        job.schedule_removal()
    await query.edit_message_text("Promemoria cancellato!")

# --- STATISTICHE ---
async def statistiche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    stats = tabella_stats.get(Q.user_id == user_id)
    if not stats or stats["totale"] == 0:
        await update.message.reply_text("Non hai ancora nessuna statistica! Inizia con /nuovo")
        return
    preferito = max(stats["per_amico"], key=stats["per_amico"].get)
    percentuale = int(stats["completati"] / stats["totale"] * 100) if stats["totale"] > 0 else 0
    testo = (
        f"📊 *Le tue statistiche:*\n\n"
        f"📌 Promemoria totali: *{stats['totale']}*\n"
        f"✅ Completati: *{stats['completati']}* ({percentuale}%)\n"
        f"❌ Non completati: *{stats['non_completati']}*\n"
        f"⭐ Amico preferito: *{AMICI[preferito]['nome']}*\n\n"
        f"_Continua così!_"
    )
    await update.message.reply_text(testo, parse_mode="Markdown")

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operazione annullata.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nuovo", nuovo)],
        states={
            SCEGLI_AMICO: [CallbackQueryHandler(scegli_amico)],
            SCRIVI_PROMEMORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, scrivi_promemoria)],
            SCEGLI_TIPO_TEMPO: [CallbackQueryHandler(scegli_tipo_tempo)],
            SCEGLI_UNITA: [CallbackQueryHandler(scegli_unita)],
            SCEGLI_QUANTITA: [
                CallbackQueryHandler(scegli_quantita, pattern="^q_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, scegli_quantita_testo),
            ],
            SCEGLI_ORA_PRECISA: [MessageHandler(filters.TEXT & ~filters.COMMAND, scegli_ora_precisa)],
            SCEGLI_GIORNO: [CallbackQueryHandler(scegli_giorno, pattern="^giorno_")],
        },
        fallbacks=[CommandHandler("annulla", annulla)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lista", lista))
    app.add_handler(CommandHandler("cancella", cancella))
    app.add_handler(CommandHandler("statistiche", statistiche))
    app.add_handler(CallbackQueryHandler(conferma_cancella, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(risposta_completamento, pattern="^fatto_"))
    app.add_handler(conv_handler)
    app.post_init = ripristina_promemoria

    print("Ricordino e' online!")
    app.run_polling()

if __name__ == "__main__":
    main()
