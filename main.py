import os
from uuid import uuid4
import re
from telegram import InlineQueryResultArticle, ParseMode, \
    InputTextMessageContent, ChatAction, ReplyKeyboardMarkup
import telegram
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, MessageHandler, Filters
import logging
import time
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
        s1 = Server('http://muovi.roma.it/ws/xml/autenticazione/1')
        self.token = s1.autenticazione.Accedi(os.environ['ATAC_API_KEY'], '')
        self.paline_server = Server('http://muovi.roma.it/ws/xml/paline/7')
    def get_autobus_from_fermata(self, id):
        res = self.paline_server.paline.Previsioni(self.token, "70101", 'it')
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
def start(bot, update):
    logger.info("Called start command")
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    #update.message.reply_text('Inserisci la tua fermata')
    response = atac.get_autobus_from_fermata("70101")
    update.message.reply_text(response)

def echo(bot, update):
     bot.sendMessage(chat_id=update.message.chat_id, text=update.message.text)

def location(bot, update):
    button_list = [[
        ReplyKeyboardMarkup("col 1", ...),
        ]]
    reply_markup = ReplyKeyboardMarkup(button_list)
    bot.send_message(chat_id=update.message.chat_id, text="A two-column menu", reply_markup=reply_markup)



def fermataCH(bot, update):
    logger.info("Called start command")
    update.message.reply_text("Work in progress. Presto potrai avere la lista di autobus in arrivo alla tua fermata.")

def help(bot, update):
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    update.message.reply_text('''
TrasportiRomaBot ti darà informazioni sugli autobus a Roma!
I comandi supportati sono:
/start per iniziare il bot
/fermata per sapere quali autobus sono in arrivo
/autobus per sapere dove si trova un autobus
    ''')

def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))

def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(os.environ['TELEGRAM_API_KEY'])

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text, echo))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("fermata", fermataCH))
    dp.add_handler(CommandHandler("location", location))

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
