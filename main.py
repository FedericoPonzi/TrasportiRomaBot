import os
from uuid import uuid4
import re
from telegram import InlineQueryResultArticle, ParseMode, \
    InputTextMessageContent, ChatAction, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, MessageHandler, Filters,\
 CallbackQueryHandler, ConversationHandler
from telegram.ext.dispatcher import run_async
from telegram.contrib.botan import Botan
import logging
from datetime import datetime
from atacbot import AtacBot
import dateutil.parser
import locale
from state import State


locale.setlocale(locale.LC_ALL, 'it_IT.utf8')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

class CallbackType:
    """Used for callbacks. Format type-value"""
    update_fermata = "0"
    update_percorso = "1"
    orari_autobus = "2"

## Static:
atac = AtacBot(os.environ['ATAC_API_KEY'])
states = State()
botan = Botan("ac7e9ae9-6960-46bd-ae51-4ea659716a34")

######
###Commands :
######
@run_async
def echo(bot, update):
     user_state = states.getState(update.message.chat_id)
     if user_state == State.FERMATA:
         #message location
         reply_markup = ReplyKeyboardRemove()
         update.message.reply_text("Perfetto!", reply_markup=ReplyKeyboardRemove())

         if update.message.location:
             req = atac.search_palina_from_location(update.message.location)
             if req.isSuccess:
                 keyboard = [[InlineKeyboardButton(f['nome'] + " (" + f['distanza_arrotondata'] + ")" , callback_data=CallbackType.update_fermata + "-" + f['id_palina'])] for f in req.data]
                 reply_markup = InlineKeyboardMarkup(keyboard)
             update.message.reply_text(req.message, reply_markup=reply_markup)
         else: #id palina
             fermata_ch(bot, update, [update.message.text])
     elif user_state == State.LINEA:
         autobus_ch(bot, update, [update.message.text])
     else:
         if update.message.text == None or update.message.text == "":
             update.message.text = "ok"
         bot.sendMessage(chat_id=update.message.chat_id, text=update.message.text)
     #Eventually remove the state
     states.removeState(update.message.chat_id)

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
            bot.editMessageText(text=req.message,
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
    botan.track(update.message)
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    states.removeState(update.message.chat_id)
    logger.info("Called /start command")
    update.message.reply_text("Ciao! Posso dirti la posizione degli autobus in arrivo e molto altro.\nUsa /help per una lista di comandi!")

@run_async
def fermata_ch(bot, update, args):
    botan.track(update.message)
    bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    states.removeState(update.message.chat_id)
    logger.info("Called /fermata command")
    if len(args) > 0:
        id_palina = args[0]
    else:
        location_keyboard = KeyboardButton(text="Invia Posizione", request_location=True)
        reply_markup = ReplyKeyboardMarkup( [[ location_keyboard ]])
        bot.sendMessage(chat_id=update.message.chat_id,
                  text="Qual'è il numero della fermata in cui ti trovi? In alternativa mandami la tua posizione.",
                  reply_markup=reply_markup)
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
    botan.track(update.message)
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
    else: #Errore case, hide the reply markup and retry
        states.setState(update.message.chat_id, State.LINEA)
        update.message.reply_text(req.message)
        update.message.reply_text(infoText)

@run_async
def help_ch(bot, update):
    botan.track(update.message)
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
Per info: https://bots.informaticalab.com
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
        CallbackQueryHandler(callback_query_handler),
        CommandHandler("start", start_ch),
        CommandHandler("help", help_ch),
        CommandHandler("fermata", fermata_ch, pass_args=True),
        CommandHandler("autobus", autobus_ch, pass_args=True),
        MessageHandler(Filters.all, echo)
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
