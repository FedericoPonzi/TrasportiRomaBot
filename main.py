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


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

class State:
    FERMATA = 0
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


class Emoji(object):
    autobus = "🚌"
    sad_face= "😣"

class Atac(object):
    def __init__(self, api_key):
        auth_server = Server('http://muovi.roma.it/ws/xml/autenticazione/1')
        self.token = auth_server.autenticazione.Accedi(os.environ['ATAC_API_KEY'], '')
        self.paline_server = Server('http://muovi.roma.it/ws/xml/paline/7')
        self.percorso_server = Server('http://muovi.roma.it/ws/xml/percorso/2')

    def get_percorso(self, fr, to):
        opt = { "mezzo" : 1, "piedi" : 1, "bus": True,
            "metro" : True, "ferro" : True, "carpooling": False,
            "max_distanza_bici" : 0,
            "linee_escluse" : [],
            "quando" : 0
        }
        res = self.percorso_server.percorso.Cerca(self.token, fr, to, opt, datetime.now().strftime("%Y-%m-%d %X"), "it")
        #print("Res: " + str(res))
        return res

    def get_autobus_from_fermata(self, id_palina):
        """ @Return: (bool success, string message)
            success: true if called was successful
                     false otherwise
            message: The results (either error or the buses)
        """
        try:
            res = self.paline_server.paline.Previsioni(self.token, str(id_palina), 'it')
        except Fault as e:
            if e.faultCode == 803:
                m = "Fermata Palina inesistente " + Emoji.sad_face + " Riprova a scrivermi la palina!"
            else:
                m = "Ho incontrato un errore :( forse atac non è online al momento :("
                logger.error("Errore get_autobus_from_fermata richiesta palina ", id_palina, ", errore:", e)
            return (False, m)
        m = res['risposta']['collocazione'] + "\n"
        inArrivo = res['risposta']['arrivi']
        for i in inArrivo:
            m += Emoji.autobus + " "
            m += i['linea'] + " - "
            m += i['annuncio'].replace("'", " minuti")
            m += "\n"
        return (True, m)


## Statics (for now):

atac = Atac(os.environ['ATAC_API_KEY'])
states = State()


######
###Commands :
######

@run_async
def echo(bot, update):
     if states.getState(update.message.chat_id) == State.FERMATA:
         fermata_ch(bot, update, [update.message.text])
         states.removeState(update.message.chat_id)
     else:
         bot.sendMessage(chat_id=update.message.chat_id, text=update.message.text)

@run_async
def callback_query_handler(bot, update):
    logger.info("Called callback_query_handler")
    states.removeState(update.callback_query.message.chat_id)

    query = update.callback_query
    keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=query.data)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    m = "\nAggiornate alle " + str(datetime.now().strftime("%X"))
    bot.editMessageText(text=atac.get_autobus_from_fermata(query.data)[1] + m, #should never fail c:
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                        reply_markup=reply_markup
    )

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
    keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=str(id_palina))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    req = atac.get_autobus_from_fermata(id_palina)
    if req[0]: #Se la richiesta è andata a buon fine.
        update.message.reply_text(req[1], reply_markup=reply_markup)
    else:
        states.setState(update.message.chat_id, State.FERMATA)
        update.message.reply_text(req[1])

@run_async
def autobus_ch(bot, update):
    states.removeState(update.message.chat_id)
    logger.info("Called /autobus command")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    update.message.reply_text("Work in progress. In futuro ti darò informazioni sulle posizioni degli autobus.")

@run_async
def help_ch(bot, update):
    states.removeState(update.message.chat_id)
    logger.info("Called /help command")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    update.message.reply_text('''
        TrasportiRomaBot ti darà informazioni sugli autobus a Roma!
 I comandi supportati sono:
 /start per iniziare il bot
 /fermata per sapere quali autobus sono in arrivo
 /autobus per sapere dove si trova un autobus
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
        CommandHandler("fermata", fermata_ch, pass_args=True, allow_edited=True),
        CommandHandler("autobus", autobus_ch)
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
