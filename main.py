import os
from uuid import uuid4
import re
from telegram import InlineQueryResultArticle, ParseMode, \
    InputTextMessageContent, ChatAction, ReplyKeyboardMarkup
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, MessageHandler, Filters,\
 CallbackQueryHandler, ConversationHandler
import logging
import time
from telegram.ext.dispatcher import run_async
from datetime import datetime
from xmlrpc.client import Server, Fault
from urllib.parse import urljoin
from emoji import emojize
import dateutil.parser
import locale
locale.setlocale(locale.LC_ALL, 'it_IT.utf8')


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

"""
TODO:
    * Aggiungere orari autobus (https://bitbucket.org/agenziamobilita/muoversi-a-roma/wiki/paline.Percorso)
    * Modificare lo stato: aggiungero alle callback e rimuovere riferimenti allo stato.
        * Modificare callback_handler, parsing della response e decisione su quello.
    * Aggiungere possibilità di cercare percorso
    * Aggiungere possibilità di prendere posizione come palina
    * Aggiungere stato del traffico (https://bitbucket.org/agenziamobilita/muoversi-a-roma/wiki/tempi.TempiTratta)
"""

class CallbackType:
    """Used for callbacks. Format type-value"""
    update_fermata = "0"
    update_percorso = "1"
    orari_autobus = "2"
class State:
    """Used to keep state of the conversation."""
    FERMATA = 0
    LINEA   = 1
    def __init__(self):
        self.statesDict = {}
    def getState(self, chat_id):
        if chat_id in self.statesDict:
            return self.statesDict[chat_id]
        return None
    def removeState(self, chat_id):
        if chat_id in self.statesDict:
            del self.statesDict[chat_id]
    def setState(self, chat_id, s):
        self.statesDict[chat_id] = s

class BotResponse(object):
    def __init__(self, isSuccess, message, data=None):
        self.isSuccess = isSuccess
        self.message= emojize(message, use_aliases = True)
        self.data = data

class AtacBot(object):
    """Format of returns:
    tuples of the format
    <bool req_result, str message, additional_data>
    Where req_result is the result of the request (true = fine, false= error)
    message = message to reply
    additional_data = dictionary, list with more info in case of req_result == true
    """
    def __init__(self, atac_api_key):
        self.atac_api_key = atac_api_key
        atac_api = "http://muovi.roma.it/ws/xml/"
        self.auth_server = Server(urljoin(atac_api, "autenticazione/" + "1"))
        self.paline_server = Server(urljoin(atac_api, "paline/" + "7"))
        self.percorso_server = Server(urljoin(atac_api, "percorso/" + "2"))
        self.server_resp_codes = {"expired_session" : 824, "unknown_percorso" : 807,
        "unknown_palina": 803, "linea_inesistente" : 804}
        self.__updateToken()
        self.generic_error = BotResponse(False, "Ho incontrato un errore :pensive: forse atac non è online al momento :worried:. Riprova fra poco!")

    def __updateToken(self):
        logger.info("Logging on atac's api")
        self.token = self.auth_server.autenticazione.Accedi(self.atac_api_key, "")

    def get_orari_bus(self, id_percorso):
        logger.info("get_orari_bus called")

        try:
            res = self.paline_server.paline.Percorso(self.token, str(id_percorso), "" ,datetime.now().strftime("%Y-%m-%d"), "it")
        except Fault as e:
            if e.faultCode == self.server_resp_codes['expired_session']:
                self.__updateToken()
                return self.get_percorso_info(id_percorso)
            else: ##tood unknown_percorso
                logger.error("get_percorso_info error:", e)
                return self.generic_error
        res = res['risposta']
        if res['no_orari']:
            ret = BotResponse(False, "Non ci sono orari per quel giorno :(")
        else:
            capolinea = res['percorsi'][0]['arrivo']
            lista_orari = res['orari_partenza']
            orario = ""
            for ind, i in enumerate(lista_orari):
                if len(i['minuti']) > 0:
                    orario += ":clock"+ str(((int(i['ora'])-1)%12+1)) +": "

                    for minuti in i['minuti']:
                        orario += i['ora'] + ":" + minuti
                        if ind < len(lista_orari) - 1:
                            orario += ", "
                    orario +="\n"
            m = "Queste sono le partenze da ''" + capolinea +"' per oggi "+ datetime.today().strftime("%A, %d %B") +":\n"
            m += orario
            ret = BotResponse(True, m)
        return ret
    def get_prossima_partenza(self, id_percorso):
        """ Next trip from the headline.
        """
        #atac.paline_server.paline.ProssimaPartenza(atac.token, "1978", "it")
        #{'id_richiesta': 'd90771ab7defe73b6cf5620a428d3cbb', 'risposta': '2017-05-07 13:05:00'}
        logger.info("get_prossima_partenza called")
        try:
            res = self.paline_server.paline.ProssimaPartenza(self.token, id_percorso, "it")
            data = dateutil.parser.parse(res['risposta'])
            #now = datetime.now()
            frmtstr = "%-H:%M" #TODO

            m = "La prossima partenza dal capolinea è alle "+ str(data.strftime(frmtstr)) + " :blush:"
            diff_delta = data - datetime.now()
            m += ", ovvero fra "
            if (diff_delta.days == 1):
                m+= "un giorno e "
            if (diff_delta.days > 1):
                m+= str(diff_delta.days) + " giorni e "
            diff_minutes = int(diff_delta.seconds / 60)
            hours = int(diff_minutes/60)
            minutes = diff_minutes % 60
            if hours == 1:
                m+= "un'ora "
            if hours > 1:
                m+= str(hours) + " ore"
            if minutes == 1:
                m+=" un minuto."
            if minutes > 1 :
                m+= str(minutes) + " minuti."
            ret = BotResponse(True, m)
        except Fault as e:
            if e.faultCode == self.server_resp_codes['expired_session']:
                self.__updateToken()
                return self.get_prossima_partenza(id_palina)
            elif e.faultCode == self.server_resp_codes['unknown_percorso']: #should never happen
                logger.error("Errore get_autobus_from_fermata richiesta palina ", id_palina, ", errore:", e)
                ret = "Non conosco il percorso specificato "
            else:
                logger.error("Generic error", e)
                ret = self.generic_error
        return ret

    def get_percorso_info(self, id_percorso):
        """ Get informations about a trip. A trip is basically an id which
            refers to a bus + it's direction( es: bus 218 direction Porta S.Giovanni has id 1978 )
        """
        try:
            res = self.paline_server.paline.Percorso(self.token, str(id_percorso), "" ,"", "it")
        except Fault as e:
            if e.faultCode == self.server_resp_codes['expired_session']:
                self.__updateToken()
                return self.get_percorso_info(id_percorso)
            elif e.faultCode == self.server_resp_codes['unknown_percorso']: # should never happend(never inputted)
                return BotResponse(False, "Non conosco il percorso indicato. :worried:")
            else:
                logger.error("get_percorso_info error:", e)
                return self.generic_error
        res = res['risposta']
        m = "Informazioni per la linea " + res['percorso']['id_linea'] + " direzione " + res['percorso']['arrivo'] +"\n\n"
        presente_veicolo = False
        for i in res['fermate']:
            m += " :small_blue_diamond: " + i['nome_ricapitalizzato']
            if "veicolo" in i:
                presente_veicolo = True
                m+= " - Un :bus: ha appena passato questa fermata!"
            if i['soppressa']:
                m+= " - Questa fermata è soppressa :unamused:"
            m+="\n"
        req_next_trip = self.get_prossima_partenza(id_percorso)
        if not presente_veicolo:
            m += "\n Non ho informazioni riguardanti le posizioni dei veicoli sulla linea :worried: prova ad aggiornare!\n"
        m +=  "\n" + req_next_trip.message +"\n"
        return BotResponse(True, m)

    def get_autobus_info(self, autobus):
        """ Gets informations about the directions of the bus
            Returns question about the direction of the bus.
        """
        try:
            res = self.paline_server.paline.Percorsi(self.token, str(autobus), "it")
        except Fault as e:
            if e.faultCode == self.server_resp_codes['expired_session']:
                self.__updateToken()
                return self.get_autobus_info(autobus)
            elif e.faultCode == self.server_resp_codes['linea_inesistente']:
                return BotResponse(False, "Linea inesistente :worried:")
        res = res['risposta']
        m = "Linea " + autobus + "\n"
        if res["monitorata"] == 1 and res["abilitata"]:
            m+="Linea monitorata e abilitata per ricevere informazioni sugli orari!\n"
        else:
            return BotResponse(False, "La linea non è monitorata :worried:")
        m+="In che direzione stai andando?"
        return BotResponse(True, m, res['percorsi'])

    def get_autobus_from_fermata(self, id_palina):
        """ Gets a list of busses and their distance in time/space from the stop.
        """
        try:
            res = self.paline_server.paline.Previsioni(self.token, str(id_palina), 'it')
        except Fault as e:
            if e.faultCode == self.server_resp_codes['unknown_palina']:
                m = BotResponse(False, "Fermata Palina inesistente :persevere: Riprova a scrivermi la palina!")
            elif e.faultCode == self.server_resp_codes['expired_session']:
                self.__updateToken()
                return self.get_autobus_from_fermata(id_palina)
            else:
                logger.error("Errore get_autobus_from_fermata richiesta palina ", id_palina, ", errore:", e)
                m = self.generic_error
            return m
        m = res['risposta']['collocazione'] + "\n"
        inArrivo = res['risposta']['arrivi']
        if len(inArrivo) > 0:
            for i in inArrivo:
                m += ":bus: "
                m += i['linea'] + " - "
                m += i['annuncio'].replace("'", " minuti")
                m += "\n"
        else:
            return BotResponse(False, m + "Non ci sono informazioni su autobus in arrivo :persevere:")
        return BotResponse(True, m)

    ###Unused:
    def get_percorso(self, fr, to):
        opt = { "mezzo" : 1, "piedi" : 1, "bus": True,
            "metro" : True, "ferro" : True, "carpooling": False,
            "max_distanza_bici" : 0, "linee_escluse" : [],
            "quando" : 0
        }
        try:
            res = self.percorso_server.percorso.Cerca(
                self.token, fr, to, opt,
                datetime.now().strftime("%Y-%m-%d %X"), "it")
            m = BotResponse(True, res)
        except Fault as e:
            if e.faultCode == self.server_resp_codes['expired_session']:
                self.__updateToken()
                m = BotResponse(False, lf.get_percorso())
            else:
                m = self.generic_error
        return m

    def get_linee_from_palina(self, id_palina):
        #Questo metodo restituisce l'elenco delle linee che transitano per la palina id_palina, con le relative informazioni (monitorata, abilitata)
        return self.paline.PalinaLinee(self.token, id_palina)


## Statics (for now):
atac = AtacBot(os.environ['ATAC_API_KEY'])
states = State()

######
###Commands :
######
@run_async
def echo(bot, update):
     user_state = states.getState(update.message.chat_id)
     if user_state == State.FERMATA:
         fermata_ch(bot, update, [update.message.text])
         states.removeState(update.message.chat_id)
     elif user_state == State.LINEA:
         autobus_ch(bot, update, [update.message.text])
         states.removeState(update.message.chat_id)
     else:
         bot.sendMessage(chat_id=update.message.chat_id, text=update.message.text)


@run_async
def callback_query_handler(bot, update):
    logger.info("Called callback_query_handler")
    query = update.callback_query

    c_id = query.message.chat_id
    data = query.data #in the format "state-message"
    callback_type, val = data.split("-")

    if callback_type == CallbackType.update_fermata:
        keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=data)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        req = atac.get_autobus_from_fermata(val)
        if req.isSuccess:
            m = "\nAggiornate alle " + str(datetime.now().strftime("%X"))
            bot.editMessageText(text=req.message + m,
                                chat_id=c_id,
                                message_id=query.message.message_id,
                                reply_markup=reply_markup)
        else:
            update.message.reply_text(req.message)
    elif callback_type == CallbackType.update_percorso:
        keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=data),
                    InlineKeyboardButton("Orari partenze",
                        callback_data=CallbackType.orari_autobus + "-" + val)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        req = atac.get_percorso_info(val)
        if req.isSuccess:
            m = "\nAggiornate alle " + str(datetime.now().strftime("%X"))
            bot.editMessageText(text=req.message + m,
                                chat_id=c_id,
                                message_id=query.message.message_id,
                                reply_markup=reply_markup)
        else:
            update.message.reply_text(req.message)
    elif callback_type == CallbackType.orari_autobus:
        req = atac.get_orari_bus(val)
        #reply with both error and response in the same way:
        bot.send_message(chat_id=c_id, text=req.message)

    else:
        update.message.reply_text("Non ho capito :( Probabilmente è un bug. Potresti dirlo a @FedericoPonzi? Grazie")

@run_async
def start_ch(bot, update):
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    states.removeState(update.message.chat_id)
    logger.info("Called /start command")
    update.message.reply_text("Ciao! Posso dirti la posizione degli autobus in arrivo e molto altro.\nUsa /help per una lista di comandi!")

@run_async
def fermata_ch(bot, update, args):
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    states.removeState(update.message.chat_id)
    logger.info("Called /fermata command")
    if len(args) > 0:
        id_palina = int(args[0])
    else:
        update.message.reply_text("Qual'è il numero della fermata in cui ti trovi?")
        states.setState(update.message.chat_id, State.FERMATA)
        return
    #update.message.reply_text('Inserisci la tua fermata')
    keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=CallbackType.update_fermata + "-" + str(id_palina))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    req = atac.get_autobus_from_fermata(id_palina)
    if req.isSuccess: #Se la richiesta è andata a buon fine.
        update.message.reply_text(req.message, reply_markup=reply_markup)
    else:
        states.setState(update.message.chat_id, State.FERMATA)
        update.message.reply_text(req.message)

@run_async
def autobus_ch(bot, update, args):
    states.removeState(update.message.chat_id)
    logger.info("Called /autobus command")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    infoText = "Di quale linea vorresti informazioni?"
    if len(args) > 0:
        id_autobus = str(args[0])
    else:
        update.message.reply_text(infoText)
        states.setState(update.message.chat_id, State.LINEA)
        return
    req = atac.get_autobus_info(id_autobus)
    if req.isSuccess:
        keyboard = [[InlineKeyboardButton(direzione['capolinea'] , callback_data=CallbackType.update_percorso + "-" + direzione['id_percorso'])] for direzione in req.data]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(req.message, reply_markup=reply_markup)
    else: #Errore case, hide the reply markup
        states.setState(update.message.chat_id, State.LINEA)
        update.message.reply_text(req.message)
        update.message.reply_text(infoText)
    #update.message.reply_text("Work in progress. In futuro ti darò informazioni sulle posizioni degli autobus.")

@run_async
def help_ch(bot, update):
    states.removeState(update.message.chat_id)
    logger.info("Called /help command")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    update.message.reply_text('''
        TrasportiRomaBot ti darà informazioni sugli autobus a Roma!
         I comandi supportati sono:
         /start per iniziare il bot
         /fermata quali autobus sono in arrivo
         /autobus orari e informazioni su una linea
         Tutte le info su cui mi baso sono di Atac, per questo motivo è colpa loro se sono imprecise.
         Per info: http://bots.informaticalab.com
         Per feedback: @FedericoPonzi
''')

@run_async
def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))
    #TODO: Handle this.

def main():
    updater = Updater(os.environ['TELEGRAM_API_KEY'], workers=32)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    handlers = [
        MessageHandler(Filters.text, echo),
        CallbackQueryHandler(callback_query_handler),
        CommandHandler("start", start_ch),
        CommandHandler("help", help_ch),
        CommandHandler("fermata", fermata_ch, pass_args=True),
        CommandHandler("autobus", autobus_ch, pass_args=True)
    ]
    for i in handlers:
        dp.add_handler(i)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    logger.info("Going idle..")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
