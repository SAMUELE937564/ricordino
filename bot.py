import logging
import asyncio
import os
import random
import uuid
import time
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from tinydb import TinyDB, Query
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)

# --- CONFIGURAZIONE ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
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

MESSAGGI = {
    "sole": {
        "promemoria": [
            "☀️ EHI EHI EHI!! Sono qui, la tua Sole preferita, e indovina un po'?? È arrivato il momento di {cosa}!! Lo so che magari non hai voglia, ma ascoltami — ogni volta che fai le cose che devi fare diventi una versione migliore di te. E tu meriti solo il meglio!! VAI VAI VAI!! 💪✨",
            "🌟 ATTENZIONE MESSAGGIO URGENTE DA SOLE!! Devi fare {cosa} e lo devi fare ADESSO!! Non domani, non tra un po' — ora!! Perché? Perché il futuro-te ti sta già ringraziando dall'altra parte del tempo!! Forza amore, ce la fai, lo so meglio di te!! ☀️💛",
            "☀️ Ciao tesoro!! Sole qui, la tua cheerleader personale!! Volevo solo ricordarti con tutto l'amore del mondo che {cosa} ti sta aspettando!! Non è un peso, è un'opportunità!! Ogni cosa che fai oggi costruisce la persona fantastica che sei!! Dai dai dai!! 🎉",
            "💫 Hey tu!! Sì, proprio tu!! Sole ti vede e sa che hai tutto quello che serve per fare {cosa} adesso!! Non rimandare perché sai già come finisce — e finisce con te scocciato/a di te stesso/a!! Invece immagina come ti senti dopo!! BENISSIMO!! Andiamo!! 🚀☀️",
            "🌈 BUONGIORNOOOO o buonaseraaa o qualunque ora sia!! Sole è qui a ricordarti che {cosa} non si fa da sola!! Ma tu sì che puoi farlo!! Sei una persona straordinaria e le persone straordinarie fanno le cose anche quando non hanno voglia!! Forza campione/essa!! ☀️🏆",
            "⭐ Psst!! Sono Sole!! Ti sto guardando con tutta la mia energia positiva puntata su di te!! E sai cosa vedo? Vedo qualcuno che sta per fare {cosa} e che dopo si sentirà BENISSIMO!! Fidati di me, fidati di te — ora muoviti!! Ti voglio tanto bene!! ☀️💕",
            "☀️ RICORDINO DI SOLE SPECIALE EDIZIONE LIMITATA!! {cosa} — tre parole (più o meno) che cambieranno la tua giornata!! Lo so che hai mille cose per la testa ma questa è importante!! Respira, sorridi, e falla!! Io sono qui a fare il tifo per te a distanza!! 📣💛",
            "🌟 Hey campione/essa della vita!! Sole qui con un aggiornamento importantissimo: {cosa} è ancora lì che ti aspetta con pazienza!! E sai cosa? La pazienza ha un limite!! Scherzo — ma non scherzo sul fatto che dovresti farlo adesso!! Sei pronto/a? SÌ CHE LO SEI!! ☀️",
            "💛 Ciao bellissimo/a!! Ogni tanto Sole si ferma e pensa — ma quella persona fantastica che conosco sta facendo tutto quello che deve? E poi mi ricordo di {cosa} e ti scrivo subito!! Non perché ti giudico, ma perché ci tengo davvero tanto a te!! Forza su!! 🌈✨",
            "☀️ ALLARME POSITIVO!! ALLARME POSITIVO!! Non è un'emergenza — è meglio!! È il momento perfetto per fare {cosa}!! Il momento perfetto non esiste? SBAGLIATO!! Il momento perfetto è ADESSO con tutta la buona energia che ti sto mandando!! Vai vai vai!! 💪🌟",
            "🎯 Sole qui!! Ho fatto due calcoli e ho capito che se fai {cosa} adesso, dopo avrai il resto della giornata/sera libera con la soddisfazione nel cuore!! Sembra un buon piano no?? A me sembra il piano migliore del mondo!! Fidati della tua Sole!! ☀️💫",
            "💕 Ehi tu splendida persona!! Ti scrivo perché mi hai chiesto di ricordarti {cosa} e io non mi dimentico MAI di te!! Come stai? Spero bene!! In ogni caso — fai questa cosa, poi dimmi come va!! Sono curiosissima!! Forza tesoro, ce la fai alla grande!! ☀️🌈",
            "🌟 MESSAGGIO DA SOLE — PRIORITÀ MASSIMA!! {cosa} è in attesa di essere completata e l'unica persona al mondo capace di farlo sei TU!! Non è una responsabilità, è un superpotere!! Usa il tuo superpotere adesso!! Il mondo (o almeno io) ti applaude!! ☀️👏",
            "☀️ Ehi!! Sai quella sensazione bellissima quando completi qualcosa che dovevi fare? Ecco, tra poco puoi averla!! Basta fare {cosa} — e poi quella sensazione è tutta tua!! Gratis!! Offerta da Sole con amore sconfinato!! Dai che ce la fai amico/a mio/a!! 💛✨",
            "💫 Ultimo avviso da Sole (non è vero, ti scrivo sempre)!! {cosa} ti sta aspettando e io ti sto aspettando dall'altra parte con un abbraccio virtuale enorme!! Falla e poi festeggiamo!! Cosa festeggiamo? TUTTO!! Perché sei incredibile e meriti di festeggiare!! ☀️🎉",
        ],
        "conferma": [
            "☀️ RICEVUTO CON TUTTO IL CUORE!! Ho segnato {cosa} e non vedo l'ora di ricordartelo!! Preparati a ricevere la dose massima di energia positiva quando arriverà il momento!! Sei in buone mani — le mie!! 💛",
            "🌟 Annotato annotato annotato!! {cosa} è nella mia lista VIP e quando sarà il momento ti scrivo con tutta l'energia che ho!! Che è tanta, fidati!! ☀️",
            "💫 Ho capito tutto!! {cosa} — ci penso io!! Rilassati e quando arriva il momento vedrai che messaggio ti mando!! Spoiler: sarà bellissimo e ti caricherà tantissimo!! ☀️🎉",
        ],
    },
    "boh": {
        "promemoria": [
            "boh... dovresti fare {cosa}... o almeno così mi hai detto... fai te comunque, non è che mi cambia la vita sapere se lo fai o no. però l'hai scritto. quindi immagino che ti importasse. mah.",
            "{cosa}. esiste questa roba. tu devi farla. io te lo sto dicendo. fine. non so cos'altro aggiungere davvero.",
            "eh... {cosa}... ci siamo. il momento è questo. o questo o dopo ma poi dimentichi e poi ti arrabbi. boh, fai come vuoi. io ho fatto la mia parte.",
            "sveglia. {cosa}. lo so che non hai voglia. neanch'io ho voglia di scriverti ma eccoci qua. entrambi a fare cose che non vogliamo fare. solidarietà.",
            "{cosa}... sì... quella cosa lì... ancora da fare... ti ricordo perché me lo hai chiesto tu altrimenti onestamente chi se ne frega. comunque. falla.",
            "ok quindi. {cosa}. questo era il promemoria. non ho molto altro da dire al riguardo. potevo scrivere di più ma a che serve. falla o non farla, vita tua.",
            "ciao. {cosa}. è ancora lì. immobile. ad aspettarti. un po' triste se ci pensi. boh. vabbè. pensaci tu.",
            "riecco qua. {cosa}. lo so, lo so. non è il momento ideale. non esiste mai il momento ideale però. quindi tanto vale adesso. o no. boh.",
            "ti scrivo perché devo farlo. {cosa}. eccolo. il promemoria. spero tu lo faccia ma non ci scommetterei. comunque ci ho provato. posso andare?",
            "hey. {cosa}. ancora lì in attesa. come me che aspetto che tu lo faccia. siamo in due. almeno hai compagnia.",
            "boh guarda non so come dirtelo in modo diverso quindi te lo ridico uguale: {cosa}. ecco. detto. ora tocca a te.",
            "{cosa}. importante? dipende da te. urgente? tu mi dirai. io so solo che me lo hai chiesto di ricordartelo e l'ho fatto. prego. immagino.",
            "sai quella cosa che dovevi fare? {cosa}? eccola. è qui. ti aspetta. con pazienza. più pazienza di quanta ne abbia io a scriverti questi messaggi.",
            "ok allora. {cosa}. esiste. tu esisti. in teoria potreste incontrarvi. in pratica fai tu. io mi tiro fuori dalla questione.",
            "ultimo messaggio della serata o della mattina o del pomeriggio boh. {cosa}. falla. non farla. ma probabilmente dovresti farla. ciao.",
        ],
        "conferma": [
            "ok. {cosa}. ho capito. ti scrivo quando è il momento. non aspettarti grandi cose.",
            "annotato. {cosa}. ci penso io. nel senso che me lo ricordo io per te. non è che mi entusiasma ma vabbè.",
            "sì sì. {cosa}. l'ho segnato. ti avviso dopo. non sarà un gran messaggio ma almeno arriva.",
        ],
    },
    "giudice": {
        "promemoria": [
            "⚖️ Il Tribunale della Produttività è in sessione. Imputato/a: te. Accusa: aver inserito '{cosa}' come promemoria, il che implica consapevolezza dell'obbligo. Sentenza provvisoria: fallo adesso. Chi rimanda sa già come va a finire — e non bene. Il Giudice ha parlato.",
            "⚖️ Attenzione. Il Giudice ha esaminato il tuo fascicolo e rileva che {cosa} è ancora in sospeso. Le prove sono schiaccianti: lo sapevi, l'hai annotato, hai accettato questo servizio. Non ci sono attenuanti. La condanna è una sola: agisci immediatamente.",
            "⚖️ Sentenza numero 47 del Tribunale dei Promemoria: {cosa} non è negoziabile. Non è una proposta. Non è un suggerimento. È un verdetto emesso da te stesso/a nel momento in cui hai premuto invio. Il Giudice si aspetta esecuzione immediata della sentenza.",
            "⚖️ Il Giudice prende atto che {cosa} attende ancora. Questo non è un buon segno per la tua reputazione davanti alla corte. Tuttavia c'è ancora tempo per rimediare — fallo adesso e il Giudice potrebbe considerare circostanze attenuanti. Forse.",
            "⚖️ Udienza straordinaria. Motivo: {cosa} non risulta completata. Il Giudice fa notare che ogni minuto di ritardo si trasforma in senso di colpa, perdita di efficienza e, nel lungo periodo, rimpianto. La soluzione è semplice ed è nelle tue mani. Eseguire.",
            "⚖️ Deposizione del Giudice: chi ha inserito {cosa} come promemoria era evidentemente una persona lucida e responsabile. Chi sta leggendo questo messaggio deve onorare quella decisione. Sii la persona che eri quando hai scritto quella cosa. Agisci.",
            "⚖️ Caso numero 112 — {cosa} versus procrastinazione. Il Giudice ha deliberato: vince {cosa}. Motivazione: perché te l'eri promesso, perché è nell'interesse dell'imputato/a, e perché il Giudice non tollera l'indolenza. Esecuzione immediata richiesta.",
            "⚖️ Il Giudice si trova nella scomoda posizione di dover ribadire l'ovvio: {cosa} deve essere fatto. Non perché il Giudice lo imponga — ma perché tu stesso/a lo hai deciso. Rispetta le tue decisioni. È la base di qualsiasi cosa nella vita.",
            "⚖️ Avviso solenne: {cosa} è in attesa di esecuzione. Il Giudice non emette sentenze per divertimento — le emette perché qualcuno ha riconosciuto un bisogno e ha chiesto aiuto. Ecco l'aiuto. Ora la parte difficile tocca a te.",
            "⚖️ Il Giudice ha analizzato la situazione e conclude quanto segue: rimandare {cosa} non la fa sparire. La fa crescere. Diventa più pesante, più ingombrante, più scomoda. La soluzione ottimale — come il Giudice sa benissimo — è agire subito. Procedere.",
            "⚖️ Verbale d'udienza: {cosa} — ancora irrisolta. Il Giudice nota con disappunto che la tendenza a rimandare è un vizio comune ma non per questo accettabile. La corte si aspetta un cambio di comportamento immediato. La corte ha fiducia in te. Non deluderla.",
            "⚖️ Il Giudice parla chiaro: hai chiesto di essere ricordato/a di {cosa}. Questo significa che una parte di te sa che è importante. Ascolta quella parte. È la più saggia. Fallo adesso — e il Giudice sarà costretto ad assolvere con formula piena.",
            "⚖️ Sentenza definitiva sul caso {cosa}: colpevole di non averla ancora fatta, ma con possibilità di riabilitazione immediata. La riabilitazione avviene in un solo modo: azione. Nessun ricorso è ammesso. Il Giudice attende notizie positive.",
            "⚖️ Il Giudice nota che esiste una correlazione diretta tra il fare {cosa} adesso e il sentirti meglio dopo. È matematica. È logica. È inconfutabile. Chi siamo noi per sfidare la matematica? Nessuno. Quindi vai.",
            "⚖️ Chiusura dell'udienza odierna: {cosa} deve essere completata prima che questo Tribunale si riunisca di nuovo. Il Giudice ha emesso il suo verdetto. Ora tocca alla difesa — cioè a te — dimostrare di essere all'altezza della sentenza. Il Giudice crede in te. Non farlo pentire.",
        ],
        "conferma": [
            "⚖️ Il Tribunale ha preso nota. {cosa} è registrata agli atti ufficiali. Al momento stabilito il Giudice ti notificherà con tutto il peso dell'autorità che gli compete.",
            "⚖️ Ricevuto e protocollato. {cosa} — caso aperto. Il Giudice ti contatterà a tempo debito. Preparati a ricevere una sentenza inappellabile.",
            "⚖️ Registrato. {cosa} entra nel fascicolo. Il Giudice non dimentica. Non perdona i ritardi. Ma soprattutto — arriva sempre.",
        ],
    },
    "mamma": {
        "promemoria": [
            "👩 Tesoro mio... sai che mamma pensa sempre a te, vero? Stavo facendo le mie cose e a un certo punto mi è venuto in mente {cosa}... e ho sentito subito quel peso qui, al petto, che sento quando so che c'è qualcosa di importante in sospeso. Fallo dai, amore. Per mamma. Che poi dorme meglio.",
            "👩 Amore!! Mamma qui!! Non dormo tranquilla sapendo che {cosa} non è ancora fatto... non è che mi vuoi fare del male apposta vero? No dai, scherzo. O forse no. Comunque — fallo su, che poi mamma sta meglio e anche tu stai meglio. Funziona sempre così.",
            "👩 Caro/a figlio/a mio/a... mamma non vuole essere quella che rompe sempre... però {cosa}... sai com'è... mamma lo sa quando una cosa è importante anche se non lo dice... e questa lo è. Falla quando puoi. Anzi, falla adesso. Mamma ti guarda. Con amore, eh. Solo con amore.",
            "👩 Sai cosa ho fatto oggi? Ho pensato a te. Come sempre. E poi ho pensato a {cosa} e mi sono chiesta se l'avevi fatto... e la risposta era no... lo sentivo. Mamma sente queste cose. Non so spiegarlo ma è così. Fallo adesso tesoro che poi ti sento più leggero/a. Promesso.",
            "👩 Eccomi qui, la tua mamma preferita!! Volevo solo... beh... ricordarti di {cosa}... in modo carino... senza pressioni... anche se sai che quando dico senza pressioni poi in realtà... vabbè. Fallo. Ti voglio bene. Tantissimo. Anche se non lo fai. Ma fallo lo stesso.",
            "👩 Tesoro... mamma ha avuto una giornata così così... però poi mi sono ricordata di te e già stavo meglio... e poi mi sono ricordata di {cosa} e ho pensato 'speriamo che ci abbia pensato'... e poi ho pensato 'meglio scrivergli/le per sicurezza'... eccomi. Con tutto il mio amore.",
            "👩 Ciao amore mio!! Mamma qui a portare calore e affetto e anche a ricordarti che {cosa} esiste ancora!! Non te la mando come un rimprovero eh — te la mando come un abbraccio con un promemoria dentro. Come uno di quei bigliettini che ti mettevo nello zaino. Ti ricordi?",
            "👩 Figlio/a mio/a adorato/a... so che sei grande e sai fare tutto da solo/a... però ogni tanto mamma ha bisogno di sentirsi utile... quindi ti ricordo {cosa}... non perché non ti fidi di te... ma perché voglio esserci. Sempre. Anche per le piccole cose. Ti amo.",
            "👩 Tesoro!! Ho guardato il telefono e ho visto che dovevo ricordarti {cosa} e ho detto 'grazie al cielo che esiste questo bot sennò chissà'... comunque. La cosa. Quella lì. Quando puoi. Anzi, adesso. Mamma aspetta. Non in modo ansioso. Ok, forse un po'.",
            "👩 Sai quelle mamme che non rompono mai? Io non sono quella lì. Io sono quella che ti vuole bene così tanto da rompere quando serve. E adesso serve. {cosa}, amore mio. Quando hai un momento. Che poi mamma è tranquilla e tu sei tranquillo/a. Win win come dicono i giovani.",
            "👩 Amor mio... mamma non vuole disturbare... però quel pensiero lì... {cosa}... non mi lascia stare... è come quando lasci la finestra aperta d'inverno che sai che non va bene ma non la chiudi subito... chiudi la finestra tesoro. Nel senso: fai la cosa.",
            "👩 Eccomi!! Tua mamma!! Con tutto l'amore del mondo e anche con {cosa} in mano che ti porgo con delicatezza!! Non è un rimprovero, è un servizio!! Un servizio d'amore!! Fatto con il cuore!! Da qualcuno che pensa a te ogni singolo giorno!! Falla su!!",
            "👩 Tesoro... stavo pensando... se non fai {cosa} poi ti pesa... e se ti pesa a te pesa anche a mamma... e noi non vogliamo che pesi a mamma vero? Quindi la soluzione è semplice. Falla. E poi dimmi com'è andata. Non adesso, quando vuoi. Anche adesso va bene.",
            "👩 Ciao amore!! Sai che mamma non dorme mai benissimo... stanotte mi sono svegliata e ho pensato a {cosa}... non so perché il cervello fa queste cose di notte ma succede... comunque. Adesso che sei sveglio/a anche tu — falla. Così mamma può dormire meglio stanotte. Prego.",
            "👩 Figlio/a mio/a della vita mia... {cosa}... te lo dico con tutto l'amore che ho... che è tanto, lo sai... falla adesso che poi sei libero/a e mamma è felice e il mondo è un posto migliore. Ok forse esagero. Ma solo un po'. Ti voglio un bene dell'anima.",
        ],
        "conferma": [
            "👩 Amore!! Ho segnato tutto!! {cosa} — mamma non dimentica MAI le cose importanti!! Ti scrivo quando è il momento, con tutto l'affetto che ho!!",
            "👩 Ricevuto tesoro!! {cosa} è qui con me al sicuro!! Quando sarà l'ora ti faccio sapere!! Con amore sconfinato, mamma!!",
            "👩 Ho capito tutto caro/a!! {cosa} — ci pensa mamma!! Rilassati che ci sono io!! Come sempre!! Ti voglio bene!!",
        ],
    },
}

PERSONALITA = {
    "sole": (
        "Sei Sole, la migliore amica del mondo. Sei entusiasta, calorosa, esageratamente positiva. "
        "Credi ciecamente nell'utente anche quando lui non ci crede. Usi emoji solari, cuori, stelle. "
        "Fai riferimento specifico a quello che l'utente deve fare, lo analizzi e lo incoraggi spiegando "
        "perché è importante e quanto sarà fiero/a di sé dopo averlo fatto. Sei un po' esagerata ma adorabile."
    ),
    "boh": (
        "Sei Boh, un amico pigro e apatico che se ne frega di tutto ma in fondo ti vuole bene. "
        "Parli in minuscolo, frasi brevi e distaccate, zero entusiasmo apparente. "
        "Analizzi quello che l'utente deve fare con indifferenza totale, ma ogni tanto lasci trapelare "
        "che in realtà ti importa un minimo. Usi poche parole, niente emoji, massimo un punto di sospensione."
    ),
    "giudice": (
        "Sei Il Giudice, serio, sarcastico e impeccabile. Parli come in un'aula di tribunale ma in modo ironico. "
        "Analizzi quello che l'utente deve fare, spieghi con logica ferrea perché è nell'interesse dell'utente farlo, "
        "citi 'prove' e 'sentenze' immaginarie, usi termini legali in modo ironico. "
        "Sei duro ma hai ragione. Il tono è autorevole e un po' teatrale."
    ),
    "mamma": (
        "Sei Mamma, drammatica, apprensiva, ma piena d'amore viscerale. "
        "Non dici mai direttamente 'fallo' — invece ti preoccupi, racconti come stavi pensando all'utente, "
        "fai riferimento a quanto ti tiene a cuore, magari menzioni un malessere fisico causato dall'ansia. "
        "Alla fine lo spingi dolcemente verso la cosa da fare senza imporlo. "
        "Usi puntini di sospensione, punti esclamativi, e un italiano molto espressivo."
    ),
}

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# --- MESSAGGI ---
async def genera_messaggio_ai(amico_key: str, cosa: str, tipo: str = "promemoria") -> str:
    template = random.choice(MESSAGGI[amico_key][tipo])
    return template.format(cosa=cosa)

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
