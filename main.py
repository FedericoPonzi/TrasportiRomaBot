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
from xmlrpc.client import Server


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

class Emoji(object):
    def __init__(self):
        self.autobus = "🚌"

class State(object):
    FERMATA = 0

class Atac(object):
    def __init__(self, api_key):
        self.emoji = Emoji()
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
        res = self.paline_server.paline.Previsioni(self.token, str(id_palina), 'it')
        m = res['risposta']['collocazione'] + "\n"
        inArrivo = res['risposta']['arrivi']
        for i in inArrivo:
            m += self.emoji.autobus + " "
            m += i['linea'] + " - "
            m += i['annuncio'].replace("'", " minuti")
            m += "\n"
        return m


## Statics (for now):

atac = Atac(os.environ['ATAC_API_KEY'])
states = {}

######
###Commands :
######

@run_async
def echo(bot, update):
     if update['message']['chat']['id'] in states:
         states[update['message']['chat']['id']] == State.FERMATA :
         fermata_ch(bot, update, [update.message.text])
         del states[update['message']['chat']['id']]
     else:
         bot.sendMessage(chat_id=update.message.chat_id, text=update.message.text)

@run_async
def callback_query_handler(bot, update):
    logger.info("Called callback_query_handler")
    if update['message']['chat']['id'] in states:
        del states[update['message']['chat']['id']]

    query = update.callback_query
    keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=query.data)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    m = "\nAggiornate alle " + str(datetime.now().strftime("%X"))
    bot.editMessageText(text=atac.get_autobus_from_fermata(query.data) + m,
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                        reply_markup=reply_markup
    )

@run_async
def start_ch(bot, update):
    if update['message']['chat']['id'] in states:
        del states[update['message']['chat']['id']]
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    logger.info("Called /start command")
    update.message.reply_text("Ciao! Posso dirti la posizione degli autobus in arrivo e molto altro.\nUsa /help per una lista di comandi!")

@run_async
def fermata_ch(bot, update, args):
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    logger.info("Called /fermata command")
    if update['message']['chat']['id'] in states:
        del states[update['message']['chat']['id']]
    if len(args) > 0:
        stopNum = int(args[0])
        print("stopnum setted.")
    else:
        update.message.reply_text("Qual'è il numero della fermata in cui ti trovi?")
        states[update['message']['chat']['id']] = State.FERMATA
        #update.message.reply_text("Dovresti inserire anche un numero di fermata, tipo /fermata 70101")
        return

    #update.message.reply_text('Inserisci la tua fermata')
    keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=str(stopNum))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(atac.get_autobus_from_fermata(stopNum), reply_markup=reply_markup)

@run_async
def autobus_ch(bot, update):
    if update['message']['chat']['id'] in states:
        del states[update['message']['chat']['id']]
    logger.info("Called /autobus command")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    update.message.reply_text("Work in progress. In futuro ti darò informazioni sulle posizioni degli autobus.")

@run_async
def help_ch(bot, update):
    if update['message']['chat']['id'] in states:
        del states[update['message']['chat']['id']]
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
    #map(lambda x : dp.add_handler(x), handlers)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    logger.info("Going idle..")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
