import os
from uuid import uuid4
import re
from telegram import InlineQueryResultArticle, ParseMode, \
    InputTextMessageContent, ChatAction, ReplyKeyboardMarkup
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
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

atac = Atac(os.environ['ATAC_API_KEY'])

# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.



######
###Commands :
######

@run_async
def echo(bot, update):
     bot.sendMessage(chat_id=update.message.chat_id, text=update.message.text)

@run_async
def callback_query_handler(bot, update):
    logger.info("Called callback_query_handler")
    query = update.callback_query
    keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=query.data)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    m = "\nAggiornate alle ore: " + str(datetime.now())
    bot.editMessageText(text=atac.get_autobus_from_fermata(query.data) + m,
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                        reply_markup=reply_markup
    )

@run_async
def start_ch(bot, update):
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    logger.info("Called /start command")
    update.message.reply_text("Ciao! Posso dirti la posizione degli autobus in arrivo e molto altro.\nUsa /help per una lista di comandi!")

@run_async
def fermata_ch(bot, update, args):
    logger.info("Called /fermata command")
    if len(args) > 0:
        stopNum = int(args[0])
    else:
        update.message.reply_text("Dovresti inserire anche un numero di fermata, tipo /fermata 70101")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    #update.message.reply_text('Inserisci la tua fermata')
    keyboard = [[InlineKeyboardButton("Aggiorna", callback_data=str(stopNum))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(atac.get_autobus_from_fermata(stopNum), reply_markup=reply_markup)

@run_async
def autobus_ch(bot, update):
    logger.info("Called /autobus command")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    update.message.reply_text("Work in progress. In futuro ti darò informazioni sulle posizioni degli autobus.")

@run_async
def help_ch(bot, update):
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
    # Create the Updater and pass it your bot's token.
    updater = Updater(os.environ['TELEGRAM_API_KEY'], workers=32)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text, echo))
    dp.add_handler(CallbackQueryHandler(callback_query_handler))
    dp.add_handler(CommandHandler("start", start_ch))
    dp.add_handler(CommandHandler("help", help_ch))
    dp.add_handler(CommandHandler("fermata", fermata_ch, pass_args=True, allow_edited=True))
    #dp.add_handler(CommandHandler("location", location))
    dp.add_handler(CommandHandler("autobus", autobus_ch))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()
    logger.info("Going idle..")

    # Block until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
