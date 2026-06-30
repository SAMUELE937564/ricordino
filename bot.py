import logging
import asyncio
import os
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

# --- DATABASE ---
db = TinyDB("ricordino_db.json")
tabella_promemoria = db.table("promemoria")
Promemoria = Query()

logging.basicConfig(level=logging.INFO)

# Stati conversazione
SCEGLI_AMICO, SCRIVI_PROMEMORIA, SCEGLI_DATA, SCEGLI_ORA = range(4)

# Personalità dei 4 amici
AMICI = {
    "sole": {
        "nome": "☀️ Sole",
        "descrizione": "Super positiva, ti carica sempre!",
        "fallback": "Ehi!! Ricordati di {cosa}!! Ce la fai, lo so!!",
    },
    "boh": {
        "nome": "🥱 Boh",
        "descrizione": "Se ne frega un po', ma ti ricorda lo stesso...",
        "fallback": "boh... {cosa}... fai te",
    },
    "giudice": {
        "nome": "⚖️ Il Giudice",
        "descrizione": "Sarcastico e spietato. La verità fa male.",
        "fallback": "Ascolta. {cosa}. Fallo. Fine.",
    },
    "mamma": {
        "nome": "👩 Mamma",
        "descrizione": "Drammatica, apprensiva, ti vuole bene in modo esagerato.",
        "fallback": "Tesoro... {cosa}... mamma ci pensa sempre...",
    }
}

# --- AI ---
PERSONALITA = {
    "sole": "Sei Sole, un'amica super positiva, calorosa ed entusiasta. Parli con energia esagerata, usi emoji solari e punti esclamativi.",
    "boh": "Sei Boh, un amico pigro e apatico che se ne frega di tutto. Parli in minuscolo, frasi corte, zero entusiasmo.",
    "giudice": "Sei Il Giudice, serio e sarcastico. Parli come un giudice di tribunale in modo ironico e diretto.",
    "mamma": "Sei Mamma, apprensiva e drammatica ma piena d'amore. Usi tanti puntini di sospensione e punti esclamativi.",
}

async def genera_messaggio_ai(amico_key: str, cosa: str, tipo: str = "promemoria") -> str:
    if tipo == "conferma":
        istruzione = (
            f"L'utente ha appena impostato un promemoria per: '{cosa}'\n\n"
            f"Scrivi UN SOLO messaggio brevissimo (massimo 2 righe) per confermare che HAI RICEVUTO la richiesta "
            f"e che lo ricorderai. Nel tuo tono caratteristico. Non dire quando arriverà il promemoria."
        )
    else:
        istruzione = (
            f"L'utente deve fare questa cosa: '{cosa}'\n\n"
            f"Scrivi UN SOLO messaggio di promemoria in italiano, massimo 3 righe, nel tuo tono caratteristico. "
            f"Non iniziare con 'Ciao' o il nome dell'utente. Vai dritto al punto."
        )
    prompt = f"{PERSONALITA[amico_key]}\n\n{istruzione}"
    try:
        risposta = await asyncio.to_thread(lambda: gemini.generate_content(prompt))
        return risposta.text.strip()
    except Exception:
        return AMICI[amico_key]["fallback"].format(cosa=cosa)

# --- MANDA PROMEMORIA ---
async def manda_promemoria(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data

    # Suoneria
    suoneria = os.path.join(os.path.dirname(__file__), "suonerie", f"{data['amico']}.wav")
    if os.path.exists(suoneria):
        with open(suoneria, "rb") as f:
            await context.bot.send_voice(chat_id=data["chat_id"], voice=f)

    # Messaggio AI
    messaggio = await genera_messaggio_ai(data["amico"], data["cosa"])
    await context.bot.send_message(chat_id=data["chat_id"], text=messaggio)

    # Rimuovi dal database dopo che è scattato
    tabella_promemoria.remove(Promemoria.job_id == data["job_id"])

# --- RIPRISTINA PROMEMORIA AL RIAVVIO ---
async def ripristina_promemoria(app):
    import time
    ora = time.time()
    tutti = tabella_promemoria.all()
    ripristinati = 0
    for p in tutti:
        secondi_rimasti = p["scatta_a"] - ora
        if secondi_rimasti <= 0:
            # Già scaduto mentre il bot era spento — manda subito
            secondi_rimasti = 5
        app.job_queue.run_once(
            manda_promemoria,
            secondi_rimasti,
            data={
                "user_id": p["user_id"],
                "cosa": p["cosa"],
                "amico": p["amico"],
                "chat_id": p["chat_id"],
                "job_id": p["job_id"],
            },
            name=p["job_id"]
        )
        ripristinati += 1
    if ripristinati:
        print(f"Ripristinati {ripristinati} promemoria dal database.")

# --- COMANDI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Ciao! Sono *Ricordino* — il promemoria che ti scrive come un amico vero!\n\n"
        "📌 /nuovo — aggiungi un promemoria\n"
        "📋 /lista — vedi i tuoi promemoria attivi\n"
        "🗑 /cancella — cancella un promemoria\n"
        "❓ /help — come funziona",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔔 *Come funziona Ricordino:*\n\n"
        "1️⃣ Scrivi /nuovo\n"
        "2️⃣ Scegli chi ti ricorderà la cosa\n"
        "3️⃣ Scrivi cosa devi fare\n"
        "4️⃣ Scegli quando\n\n"
        "I tuoi amici:\n"
        "☀️ *Sole* — super positiva, ti carica\n"
        "🥱 *Boh* — se ne frega ma ti ricorda lo stesso\n"
        "⚖️ *Il Giudice* — sarcastico e spietato\n"
        "👩 *Mamma* — drammatica, apprensiva, ti ama troppo",
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
    await update.message.reply_text(
        "Chi vuoi che ti ricordi la cosa?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SCEGLI_AMICO

async def scegli_amico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amico = query.data
    context.user_data["amico"] = amico
    info = AMICI[amico]
    await query.edit_message_text(
        f"Hai scelto *{info['nome']}* — {info['descrizione']}\n\nCosa devo ricordarti? Scrivimelo!",
        parse_mode="Markdown"
    )
    return SCRIVI_PROMEMORIA

async def scrivi_promemoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = update.message.text
    context.user_data["cosa"] = testo
    keyboard = [
        [InlineKeyboardButton("⏱ Minuti", callback_data="minuti"),
         InlineKeyboardButton("🕐 Ore", callback_data="ore")],
    ]
    await update.message.reply_text(
        f"Annotato: *{testo}*\n\nIn minuti o in ore?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SCEGLI_DATA

async def scegli_unita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["unita"] = query.data
    if query.data == "minuti":
        keyboard = [
            [InlineKeyboardButton("5 min", callback_data="t_5"),
             InlineKeyboardButton("10 min", callback_data="t_10"),
             InlineKeyboardButton("15 min", callback_data="t_15")],
            [InlineKeyboardButton("20 min", callback_data="t_20"),
             InlineKeyboardButton("30 min", callback_data="t_30"),
             InlineKeyboardButton("45 min", callback_data="t_45")],
            [InlineKeyboardButton("✏️ Scrivi tu un numero", callback_data="t_custom")],
        ]
        await query.edit_message_text("Fra quanti minuti?", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard = [
            [InlineKeyboardButton("1 ora", callback_data="t_60"),
             InlineKeyboardButton("2 ore", callback_data="t_120"),
             InlineKeyboardButton("3 ore", callback_data="t_180")],
            [InlineKeyboardButton("6 ore", callback_data="t_360"),
             InlineKeyboardButton("12 ore", callback_data="t_720"),
             InlineKeyboardButton("24 ore", callback_data="t_1440")],
            [InlineKeyboardButton("✏️ Scrivi tu un numero", callback_data="t_custom")],
        ]
        await query.edit_message_text("Fra quante ore?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SCEGLI_ORA

async def programma_promemoria(context, user_id, chat_id, amico, cosa, secondi, etichetta):
    import time, uuid
    job_id = str(uuid.uuid4())
    scatta_a = time.time() + secondi

    tabella_promemoria.insert({
        "job_id": job_id,
        "user_id": user_id,
        "chat_id": chat_id,
        "amico": amico,
        "cosa": cosa,
        "scatta_a": scatta_a,
        "etichetta": etichetta,
    })

    context.application.job_queue.run_once(
        manda_promemoria, secondi,
        data={"user_id": user_id, "cosa": cosa, "amico": amico, "chat_id": chat_id, "job_id": job_id},
        name=job_id
    )
    return job_id

async def scegli_tempo_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "t_custom":
        unita = context.user_data.get("unita", "minuti")
        testo = "Scrivi quanti minuti (es. 7, 25, 50)" if unita == "minuti" else "Scrivi quante ore (es. 1, 5, 10)"
        await query.edit_message_text(testo)
        return SCEGLI_ORA

    minuti = int(query.data.replace("t_", ""))
    secondi = minuti * 60
    unita = context.user_data.get("unita", "minuti")
    etichetta = f"{minuti} minuti" if unita == "minuti" else f"{minuti // 60} ora/e"

    user_id = query.from_user.id
    amico = context.user_data["amico"]
    cosa = context.user_data["cosa"]

    await programma_promemoria(context, user_id, query.message.chat_id, amico, cosa, secondi, etichetta)

    conferma = await genera_messaggio_ai(amico, cosa, tipo="conferma")
    await query.edit_message_text(f"{AMICI[amico]['nome']} — tra {etichetta}\n\n{conferma}")
    return ConversationHandler.END

async def scegli_ora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valore = float(update.message.text.replace(",", "."))
        if valore <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Scrivi un numero valido, es. 10 o 30")
        return SCEGLI_ORA

    user_id = update.message.from_user.id
    amico = context.user_data["amico"]
    cosa = context.user_data["cosa"]
    unita = context.user_data.get("unita", "ore")

    if unita == "minuti":
        secondi = int(valore * 60)
        etichetta = f"{valore:.0f} minuti"
    else:
        secondi = int(valore * 3600)
        etichetta = f"{valore:.0f} ora/e"

    await programma_promemoria(context, user_id, update.message.chat_id, amico, cosa, secondi, etichetta)

    conferma = await genera_messaggio_ai(amico, cosa, tipo="conferma")
    await update.message.reply_text(f"{AMICI[amico]['nome']} — tra {etichetta}\n\n{conferma}")
    return ConversationHandler.END

# --- LISTA ---
async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import time
    user_id = update.message.from_user.id
    items = tabella_promemoria.search(Promemoria.user_id == user_id)
    if not items:
        await update.message.reply_text("Non hai promemoria attivi! Scrivi /nuovo per aggiungerne uno.")
        return
    testo = "📋 *I tuoi promemoria attivi:*\n\n"
    for i, p in enumerate(items, 1):
        rimasti = max(0, int(p["scatta_a"] - time.time()))
        ore = rimasti // 3600
        minuti = (rimasti % 3600) // 60
        secondi = rimasti % 60
        if ore > 0:
            tempo = f"{ore}h {minuti}m"
        elif minuti > 0:
            tempo = f"{minuti}m {secondi}s"
        else:
            tempo = f"{secondi}s"
        testo += f"{i}. _{p['cosa']}_ — {AMICI[p['amico']]['nome']} — tra *{tempo}*\n"
    await update.message.reply_text(testo, parse_mode="Markdown")

# --- CANCELLA ---
async def cancella(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    items = tabella_promemoria.search(Promemoria.user_id == user_id)
    if not items:
        await update.message.reply_text("Non hai promemoria attivi da cancellare.")
        return
    keyboard = []
    for p in items:
        label = f"❌ {p['cosa'][:30]} — {AMICI[p['amico']]['nome']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"del_{p['job_id']}")])
    await update.message.reply_text(
        "Quale promemoria vuoi cancellare?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def conferma_cancella(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    job_id = query.data.replace("del_", "")

    # Rimuovi dal database
    tabella_promemoria.remove(Promemoria.job_id == job_id)

    # Rimuovi dal job queue
    jobs = context.application.job_queue.get_jobs_by_name(job_id)
    for job in jobs:
        job.schedule_removal()

    await query.edit_message_text("Promemoria cancellato!")

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
            SCEGLI_DATA: [CallbackQueryHandler(scegli_unita)],
            SCEGLI_ORA: [
                CallbackQueryHandler(scegli_tempo_rapido, pattern="^t_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, scegli_ora),
            ],
        },
        fallbacks=[CommandHandler("annulla", annulla)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lista", lista))
    app.add_handler(CommandHandler("cancella", cancella))
    app.add_handler(CallbackQueryHandler(conferma_cancella, pattern="^del_"))
    app.add_handler(conv_handler)

    # Ripristina promemoria salvati al riavvio
    app.post_init = ripristina_promemoria

    print("Ricordino e' online!")
    app.run_polling()

if __name__ == "__main__":
    main()
