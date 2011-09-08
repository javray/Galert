import android
from time import sleep
import os, sys
import json
import threading
import socket
import xmpp
from itertools import izip, cycle
import hashlib

class Demonio(threading.Thread):
	def __init__(self):
		self._stopEvent = threading.Event()
		self._droid = android.Android()
		self._pid = 0
		self.contacts_cache = {}
		threading.Thread.__init__(self, name="Demonio")
	def getpid(self):
		return self._pid
	def stop(self):
		self._stopEvent.set()
		self._droid.sendBroadcast('com.javray.galert.STOP_THREAD', None, None, {"com.javray.galert.extra.PID": self._pid}, None, None)
	def parseEvent(self, line):
		out = json.loads(line)
		out.update(json.loads(out["data"]))
		return out
	def gtalkSend(self, user, passwd, user_not, text):
		SERVER = 'talk.google.com', 5223
		try:
		    jid = xmpp.protocol.JID(user)
		    cl = xmpp.Client(jid.getDomain(), debug=[])
		    con = cl.connect(server=SERVER)
		    auth = cl.auth(jid.getNode(), passwd, resource=jid.getResource())
		    cl.send(xmpp.protocol.Message(user_not, text))
		except:
		    self._droid.log(str(sys.exc_info()))
	def xor_crypt_string(self, data, key):
		return ''.join(chr(ord(x) ^ ord(y)) for (x,y) in izip(data, cycle(key)))
	def get_contact(self, contact):
	    contact_hash = hashlib.md5(str(contact)).hexdigest()
	    if contact_hash in self.contacts_cache:
	        contacto = self.contacts_cache[contact_hash]
	    else:
	        contacts = self._droid.queryContent('content://com.android.contacts/data/phones', ['display_name'], "substr('%s', -9) = substr(data1, -9)" % contact , None, None).result
	        if not contacts:
	            contacto = contact
	        else:
	            contacto = contacts[0]['display_name']
	        self.contacts_cache[contact_hash] = contacto
	    return contacto
class DemonioLlamadasSMS(Demonio):
    def run(self):
		pref = self._droid.prefGetValue('conf', 'galert.conf')
		conf = json.JSONDecoder().decode(pref.result)
		devid = str(self._droid.getDeviceId().result)
		self._pid = os.getpid()
		
		user = self.xor_crypt_string(conf['user'], devid)
		passwd = self.xor_crypt_string(conf['pass'], devid)
		user_not = self.xor_crypt_string(conf['user_not'], devid)
		
		ACTION_STOP = 'com.javray.galert.STOP_THREAD'
		self._droid.eventRegisterForBroadcast(ACTION_STOP, False)
		
		if conf['sms'] == 1:
			ACTION_SMS = "android.provider.Telephony.SMS_RECEIVED"
			self._droid.eventRegisterForBroadcast(ACTION_SMS, False)
		if conf['llamadas'] == 1:
			ACTION_LLAMADAS = "android.intent.action.PHONE_STATE"
			self._droid.eventRegisterForBroadcast(ACTION_LLAMADAS, False)
			sonando = 0
		
		p = self._droid.startEventDispatcher()
		s = socket.socket()
		s.connect(("localhost", p.result))
		f = s.makefile()
		
		# Variables locales fuera del bucle
		get_contact = self.get_contact
		gtalkSend = self.gtalkSend
		parseEvent = self.parseEvent
		smsGetMessages = self._droid.smsGetMessages
		
		try:
		    while not self._stopEvent.isSet():
		        event = parseEvent(f.readline())
		        data = json.loads(event['data'])
		        if data['action'] == ACTION_SMS:
		            mensajes = smsGetMessages(1)[1]
		            while mensajes == []:
		                sleep(1)
		                mensajes = smsGetMessages(1)[1]
		            for m in mensajes:
		                contacto = get_contact(m[u'address'])
		                gtalkSend(user, passwd, user_not, '%s - %s' % (contacto, m[u'body']))
		        elif data['action'] == ACTION_LLAMADAS:
		            if data['state'] == 'RINGING' and sonando == 0:
		                contacto = get_contact(data['incoming_number'])
		                gtalkSend(user, passwd, user_not, 'Llamada entrante de %s' % (contacto))
		                sonando = 1
		            elif data['state'] == 'IDLE':
		                sonando = 0
		        elif data['action'] == ACTION_STOP:
		            break
		except:
		    self._droid.log(str(sys.exc_info()))
		    self._droid.prefPutValue('conf', {'user':conf['user'], 'pass':conf['pass'], 'user_not':conf['user_not'], 'llamadas':conf['llamadas'], 'sms':conf['sms'], 'daemon_run': 'off'},'galert.conf')
		    return False
		finally:
		    s.close()
		    self._droid.stopEventDispatcher()
		    self._droid.eventUnregisterForBroadcast(ACTION_STOP)
		    if conf['sms'] == 1:
		        self._droid.eventUnregisterForBroadcast(ACTION_SMS)
		    if conf['llamadas'] == 1:
		        self._droid.eventUnregisterForBroadcast(ACTION_LLAMADAS)
		    return True
                
if __name__ == '__main__':
    # inicializamos variables
    path = os.path.dirname(sys.argv[0])
    
    # creamos el objeto Android
    droid = android.Android()
    
    # Arranco la interfaz
    droid.webViewShow('file://%s/galert.html' % (path))
    
    # Menu
    droid.addOptionsMenuItem("Acerca","menu","acerca","ic_dialog_info")
    droid.addOptionsMenuItem("Guardar","menu","guardar","ic_menu_edit")
    droid.addOptionsMenuItem("Cerrar","menu","cerrar","ic_menu_revert")
	
	# Creamos el demonio
    p = DemonioLlamadasSMS()
	
	# variables locales fuera del bucle
    eventWait = droid.eventWait
    
    # bucle de la aplicacion
    while True:
        result = eventWait().result
        if result['data'] == 'fin':
		    break
        elif result['data'] == 'daemon_start':
            p.start()
            droid.log(str(threading.enumerate()))
        elif result['data'] == 'daemon_stop':
            if p.isAlive():
                q = DemonioLlamadasSMS()
                p.stop()
                p.join()
                p = q
        elif result['data'] == 'cerrar':
            pref = droid.prefGetValue('conf', 'galert.conf')
            conf = json.JSONDecoder().decode(pref.result)
            if conf['daemon_run'] == 'off':
                break
            else:
    		    intent = droid.makeIntent("android.intent.action.MAIN", None, None, None, ['android.intent.category.HOME'], "com.android.launcher", "com.android.launcher2.Launcher").result
    		    droid.startActivityIntent(intent).result
    	elif result['data'] == 'guardar':
    	    droid.eventPost('python', 'guardar_html')
    	elif result['data'] == 'acerca':
    	    droid.dialogCreateAlert('gAlert', '(c) 2011 javray')
    	    droid.dialogSetPositiveButtonText('OK')
    	    droid.dialogShow()
        sleep(0.2)
    droid.log(str(threading.enumerate()))
    sys.exit(1)