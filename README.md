# TrasportiRomaBot
A simple bot, trying to use every up-to-date technology in order to create a bot

## Soft TODO:
  * Database to store chat logs
  * Aggiungere stato del traffico (https://bitbucket.org/agenziamobilita/muoversi-a-roma/wiki/tempi.TempiTratta)
  * Aggiungere testing

## Long TODO:
* Aggiungere possibilità di cercare percorso
* Verifica della posizione della palina
* Aggiunta dei preferiti

## Very long todo:
  Add a tutorial: message shown only the first time the users chat with the bot.

## VERY VERY VERY Long todo:
  * Groups support

## Abandoned:
  * NLP interface

DB:
user:
chat_id, username, name, surname

chat:
chat_id, message, datetime, resptype

State:
chat_id, state


state con dominio:
FERMATA = 0
LINEA   = 1
