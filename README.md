# TrasportiRomaBot

It's made with python3.


## Installation

Get an ATAC api key from [here](http://muovi.roma.it/dev/key), and add it to your environment:

    export ATAC_API_KEY=your-api-key
Get a Telegram api key from @BotFather:

    export TELEGRAM_API_KEY=your-api-key

Run build.sh to download the requirements in a new virtualenv:

    chmod +x build.sh
    ./build.sh

Load the new virtualenv:
```
source venv/bin/activate
```
and finally, run main.py:

    python3 main.py

----

## Soft TODO:
* Database to store chat logs
* Aggiungere stato del traffico (https://bitbucket.org/agenziamobilita/muoversi-a-roma/wiki/tempi.TempiTratta)
* Add testing

## Long TODO:
* Aggiungere possibilità di cercare percorso
* Add favorite stops.

## Very long todo:
 * Add a tutorial: message shown only the first time the users chat with the bot.

## VERY VERY VERY Long todo:
* Groups support    

## Abandoned:
* NLP interface: Using api.ai. I think it's easier to use the telegram's commands for *this* use case.
