# TrasportiRomaBot
A simple bot, trying to use *some* up-to-date technology for bot developing. 

Sorry for mixing up italian and english
:(

Made in python3, setup ATAC_API_KEY:

`export ATAC_API_KEY=your-api-key`
and Telegram api key:

`export TELEGRAM_API_KEY=your-api-key`

Run build.sh:
```
chmod +x build.sh
./build.sh
```
Load the new env:
```
source venv/bin/activate
```
and finally, run main.py:

```
python3 main.py
```

----

## Soft TODO:
* Database to store chat logs
* Aggiungere stato del traffico (https://bitbucket.org/agenziamobilita/muoversi-a-roma/wiki/tempi.TempiTratta)
* Add testing

## Long TODO:
* Aggiungere possibilità di cercare percorso
* Add favorite stops.

## Very long todo:
Add a tutorial: message shown only the first time the users chat with the bot.

## VERY VERY VERY Long todo:
* Groups support

## Abandoned:
* NLP interface: Using api.ai. I think it's easier to use the telegram's commands for *this* use case.
