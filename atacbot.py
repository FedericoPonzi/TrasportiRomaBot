from xmlrpc.client import Server, Fault
import logging
from urllib.parse import urljoin
from emoji import emojize
import dateutil.parser
from datetime import datetime

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

class BotResponse(object):
    """ This is a response for every request to the AtacBot class
        If isSuccess is false, message it's an error.
        Self.data are additional data, and is None most of the times. It's used to build telegram's menus.
    """
    def __init__(self, isSuccess, message, data=None):
        self.isSuccess = isSuccess
        self.message= emojize(message, use_aliases = True)
        self.data = data


class AtacBot(object):
    """ This is the heart (ok, brain it's better) of the bot.
        It knows how to talk to the atac's server, and how to construct the textual responses.
    """
    def __init__(self, atac_api_key):
        self.atac_api_key = atac_api_key
        atac_api = "http://muovi.roma.it/ws/xml/"
        self.servers = {
            "auth" : Server(urljoin(atac_api, "autenticazione/" + "1")),
            "paline" : Server(urljoin(atac_api, "paline/" + "7")),
            "percorso" : Server(urljoin(atac_api, "percorso/" + "2"))
        }
        self.server_resp_codes = {"expired_session" : 824, "unknown_percorso" : 807,
        "unknown_palina": 803, "linea_inesistente" : 804}
        self.__updateToken()
        self.generic_error = BotResponse(False, "Ho incontrato un errore :pensive: forse atac non è online al momento :worried:. Riprova fra poco!")

    def __updateToken(self):
        logger.info("Logging on atac's api")
        self.token = self.servers['auth'].autenticazione.Accedi(self.atac_api_key, "")

    def search_palina_from_location(self, location = {'latitude': "41.90", 'longitude': "12.47"}):
        try:
            res = self.servers['paline'].paline.SmartSearch(self.token,"punto:("+ str(location['latitude']) +" , " + str(location['longitude']) +")")
        except Fault as e:
            if e.faultCode == self.server_resp_codes['expired_session']:
                self.__updateToken()
                return self.search_palina_from_location(location)
            else:
                logger.error("search_palina_from_location:", e)
                return self.generic_error()
        res = res['risposta']

        if res['errore']:
            m = "Mi dispiace, non ho trovato fermate vicino a te. Ma 'do stai?! :flushed:"
        else: #TODO Controllare se è una sola.
            m = "Ho trovato queste fermate vicino a te :smirk:"
        paline_extra = sorted(res['paline_extra'], key=lambda k: k.get("distanza", None))
        return BotResponse(True, m, paline_extra)


    def get_orari_bus(self, id_percorso):
        logger.info("get_orari_bus called")
        try:
            res = self.servers['paline'].paline.Percorso(self.token, str(id_percorso), "" ,datetime.now().strftime("%Y-%m-%d"), "it")
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
        #atac.servers['paline'].paline.ProssimaPartenza(atac.token, "1978", "it")
        #{'id_richiesta': 'd90771ab7defe73b6cf5620a428d3cbb', 'risposta': '2017-05-07 13:05:00'}
        logger.info("get_prossima_partenza called")
        try:
            res = self.servers['paline'].paline.ProssimaPartenza(self.token, id_percorso, "it")
            data = dateutil.parser.parse(res['risposta'])
            #now = datetime.now()
            frmtstr = "%-H:%M"

            m = "La prossima partenza dal capolinea è alle "+ str(data.strftime(frmtstr)) + " :blush:"
            diff_delta = data - datetime.now()
            diff_minutes = int(diff_delta.seconds / 60)
            hours = int(diff_minutes/60)
            minutes = diff_minutes % 60

            m += ", ovvero fra "
            if (diff_delta.days == 1):
                m+= "un giorno e "
            if (diff_delta.days > 1):
                m+= str(diff_delta.days) + " giorni e "
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
            res = self.servers['paline'].paline.Percorso(self.token, str(id_percorso), "" ,"", "it")
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
            res = self.servers['paline'].paline.Percorsi(self.token, str(autobus), "it")
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
            res = self.servers['paline'].paline.Previsioni(self.token, str(id_palina), 'it')
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
        m = res['risposta']['collocazione'].lower() + "\n"
        inArrivo = res['risposta']['arrivi']
        if len(inArrivo) > 0:
            for i in inArrivo:
                m += ":bus: "
                m += i['linea'] + " - "
                m += i['annuncio'].replace("'", " minuti")
                m += "\n"
        else:
            return BotResponse(False, m + "Non ci sono informazioni su autobus in arrivo :persevere:")
        m += "\nAggiornate alle " + str(datetime.now().strftime("%X"))
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
