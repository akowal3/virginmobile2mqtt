import os
import sys
import json
from time import sleep
import paho.mqtt.client as mqtt
from threading import Thread as t
import logging
import subprocess
import requests as r

MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
INTERVAL = int(os.getenv('INTERVAL', 60))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
VM_PHONE_IDS = os.getenv('VM_PHONE_IDS')
VM_USERNAME = os.getenv('VM_USERNAME')
VM_PASSWORD = os.getenv('VM_PASSWORD')

class Balance(dict):
  def __init__(self, quantity: float, unit: str) -> None:
    dict.__init__(self, quantity=quantity, unit=unit)

class PhoneDetails(dict):
  def __init__(self, phone_id: int, name: str, account_balance: Balance, voice_balance: Balance, text_balance: Balance, data_balance: Balance) -> None:
    dict.__init__(
      self, 
      phone_id=phone_id,
      name=name,
      account_balance=account_balance,
      voice_balance=voice_balance,
      text_balance=text_balance,
      data_balance=data_balance
    )

class VirginMobile:
  def __init__(self):
    self.username = VM_USERNAME
    self.password = VM_PASSWORD
    self.phones = self.pasrse_phone_ids()

    self.login_url = "https://virginmobile.pl/spitfire-web-api/api/v1/authentication/login"
    self.defails_url = "https://virginmobile.pl/spitfire-web-api/api/v1/selfCare/msisdnDetails"
    self.logout_url = "https://virginmobile.pl/spitfire-web-api/api/v1/authentication/logout"

    self.cookies = None

  def pasrse_phone_ids(self):
    vaild_phone_ids = filter(lambda phone_id: len(phone_id) == 11, VM_PHONE_IDS.split(','))
    return list(vaild_phone_ids)

  def login(self):
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'username': self.username, 'password': self.password}

    response = r.post(self.login_url, data=data, headers=headers)

    if response.status_code == 200:
      logging.info("Login successful")
      self.cookies = response.cookies.get_dict()
      logging.debug(f'Cookies: {json.dumps(self.cookies)}')
    else:
      logging.error(f"Login failed. Response: {response}")

  def logout(self):
    response = r.get(self.logout_url, cookies=self.cookies)

    if response.status_code == 200:
      logging.info("Logout successful")
      self.cookies = None
    else:
      logging.error(f"Logout failed. Response: {response}")

  def get_raw_details(self, phone_id):
    if(self.cookies == None):
      logging.error("Data retreival failed. Cookies are None")
      return {}

    logging.debug(f'Requesting details for {phone_id}')

    headers = {'msisdn': phone_id}

    response = r.get(self.defails_url, cookies=self.cookies, headers=headers)

    if response.status_code == 200:
      result = response.json()
      logging.info(f"Successfully retreived data for {result['name']} ({result['msisdn']})")
      return result
    else:
      logging.error(f"Data retrieval failed. Code: {response.status_code}, Message: {response.text}")

  def extract_balance(self, json, balance_name):
    balance_node = json['customerBalancesDto'][balance_name]
    return Balance(balance_node['quantity'], balance_node['unit'])

  def extract_phone_details(self, phone_id):
    json = self.get_raw_details(phone_id)

    if json is None:
      raise Exception('Endpoint returned None')

    account_balance = self.extract_balance(json, "generalBalance")
    voice_balance = self.extract_balance(json, "complexBundleVoiceBalance")
    text_balance = self.extract_balance(json, "smsBalance")
    data_balance = self.extract_balance(json, "dataBalance")

    return PhoneDetails(json['msisdn'], json['name'], account_balance, voice_balance, text_balance, data_balance)

  def extract_all_details(self):
    result = []

    try:
      self.login()
      sleep(0.1)
      for phone_id in self.phones:
        details = self.extract_phone_details(phone_id)
        result.append(details)
    finally:
      self.logout()

    return result

class Publisher:
  def __init__(self, vm: VirginMobile, client: mqtt.Client):
    self.vm = vm
    self.client = client
    self.prefix = 'virginmobile2mqtt'

  def send_status(self, status):
    try:
      self.client.publish(f'{self.prefix}/{VM_USERNAME}/status', status, 0, True)
      logging.debug('Sending MQTT status')
    except Exception as e:
      logging.error(f'MQTT status send failed: {e}') 

  def send_payload(self, payload, postfix):
    try:
      self.client.publish(f'{self.prefix}/{VM_USERNAME}/{postfix}', json.dumps(payload), MQTT_QOS, False)
      logging.debug(f'Sending {postfix} with payload: {payload} to MQTT')
    except Exception as e:
      logging.error(f'Message send failed: {e}')

  def publish(self):
    while True:
      try:
        all_details = self.vm.extract_all_details()
        for d in all_details:
          self.send_payload(d, d['phone_id'])
        self.send_status('online')
      except Exception as e:
        logging.error('Failed to publish', e)
        self.send_status('offline')
      sleep(INTERVAL)

def mqtt_connect() -> mqtt.Client:
  #Connect to MQTT broker and set LWT
  try:
    client = mqtt.Client(f'virginmobile2mqtt-{VM_USERNAME}')
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.will_set(f'virginmobile2mqtt/{VM_USERNAME}/status', 'offline', 0, True)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.publish(f'virginmobile2mqtt/{VM_USERNAME}/status', 'online', 0, True)
    logging.info('Connected to MQTT broker.')
    return client
  except Exception as e:
    logging.error(f'Unable to connect to MQTT broker: {e}')
    sys.exit()

if __name__ == '__main__':
  if LOG_LEVEL.lower() not in ['debug', 'info', 'warning', 'error']:
    LOG_LEVEL = 'info'
    logging.warning(f'Selected log level "{LOG_LEVEL}" is not valid; using default')

  logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s %(levelname)s: %(message)s') 

  vm = VirginMobile()
  client = mqtt_connect()
  p = Publisher(vm, client)
    
  polling_thread = t(target=p.publish, daemon=True)
  polling_thread.start()
  client.loop_forever()