# coding=utf-8
from PIL import ImageFont, Image, ImageDraw
from flask import Flask, render_template, request, send_file, redirect, url_for
from datetime import datetime
import time
import qrcode
import uuid 
import os
import pymongo
from pymongo import MongoClient
import string
import secrets
import random
import smtplib
import base64

app = Flask(__name__)
client = MongoClient()
client = MongoClient('localhost', 27017)

def randomString(stringLength=10):
    lettersAndDigits = string.ascii_lowercase + string.digits
    return ''.join(random.choice(lettersAndDigits) for i in range(stringLength))


# return an array of accolli related to a sepicific dashboard
def find_accolli_for_dashboard(dashboard_id):
  accolli = []
  db = client['cartediaccollo']
  collection = db['carte']
  cards = collection.find({"dashboard_id": dashboard_id}) 
  for doc in cards:
    accolli.append(doc)
  return accolli

# check if the dashboard exists and return a dashboard hash
def is_valid_dashboard(dashboard_id):
  db = client['cartediaccollo']
  collection = db['dashboards']
  dashboard = collection.find_one({"uuid": dashboard_id})
  if dashboard != None:
    return dashboard 
  else:
    return None

def check_valid_authorization(dashboard_id,token):
  db = client['cartediaccollo']
  collection = db['dashboards']
  dashboard = collection.find_one({"uuid": dashboard_id, "token": token})
  if dashboard != None:
    print('Dashboard' + dashboard_id + " with token " + token + " found!")
    return dashboard 
  else:
    print('Dashboard' + dashboard_id + " with token " + token + " not found!")
    return None

def generate_dashboard_id_and_token(name):
  db = client['cartediaccollo']
  collection = db['dashboards']
  dashboard_id = str(uuid.uuid4())
  while True:
    card = collection.find_one({"uuid": dashboard_id})
    if card == None:
      break
    else:
      dashboard_id = str(uuid.uuid1())
  dashboard = {"uuid": dashboard_id, "token": randomString(20), "name": name}
  print("Try to write a dasboard to MongoDB " + str(dashboard))
  if collection.insert_one(dashboard).inserted_id != None:
    return dashboard
  else:
    False

def read_card_mongo(uuid,token):
  client = MongoClient()
  client = MongoClient('localhost', 27017)
  db = client['cartediaccollo']
  collection = db['carte']
  card = collection.find_one({"uuid": uuid})
  print card
  if token != card['token']:
    return False
  else:
    return card

def write_card_mongo(card_id,token,card_url,sender,dashboard_id):
  client = MongoClient()
  client = MongoClient('localhost', 27017)
  db = client['cartediaccollo']
  collection = db['carte']
  post = {"uuid": card_id, "token": token, "status": "open", "url": card_url, "sender": sender, "dashboard_id": dashboard_id}
  post_id = collection.insert_one(post).inserted_id
  print post_id

def change_card_status(card_id,new_status):
  client = MongoClient()
  client = MongoClient('localhost', 27017)
  db = client['cartediaccollo']
  collection = db['carte']
  myquery = { "uuid": card_id }
  newvalues = { "$set": { "status": new_status } }
  return collection.update_one(myquery, newvalues)

def create_card_img(card_id,recipient,task,sender,token):
  img = Image.new('RGB', (1024, 800), color = (0, 0, 0))
  d = ImageDraw.Draw(img)
  
  font = ImageFont.truetype("Inconsolata-Regular.ttf",28)
  card_text = "Gentile " + recipient + ",\n\n\nLa presente Carta Di Accollo creata in data " + time.strftime("%d/%m/%Y") + \
  "\ncertifica che ho preso in considerazione la tua richiesta.\n\n" \
  "Io sottoscritto, " + sender + ", mi impegno ad occuparmi di:\n" + task + ".\n\n" \
  "Per favore non chiedermi troppo spesso feedback sullo stato\ndi completamento! Ci sto lavorando!\n\n"
  d.text((100,100), card_text, fill=(255,255,255),font=font)
  
  font = ImageFont.truetype("Inconsolata-Regular.ttf",24)
  details = "ID: " + card_id + "\n" \
  "Token: " + token + "\n" \
  "Scansiona il QR code per accedere alla richiesta" \
  "\n\n\n\n" + "Crea anche tu accolli certificati su https://accolli.it" 
  d.text((100,500), details, fill=(255,255,255),font=font)
  
  img.save('static/cards/' + card_id + '-text.png')
  
  qr = qrcode.QRCode(
      version=1,
      error_correction=qrcode.constants.ERROR_CORRECT_L,
      box_size=6,
      border=1,
  )

  qr_data = "https://accolli.it/show?id=" + card_id + "&token=" + token  
  print qr_data
  qr.add_data(qr_data)
  qr.make(fit=True)
  img = qr.make_image(fill_color="white", back_color="black")
  img.save('static/cards/' + card_id + '-qr.png')

  images = map(Image.open, ['static/cards/' + card_id + '-text.png','static/cards/' + card_id + '-qr.png'])
  widths, heights = zip(*(i.size for i in images))

  total_width = sum(widths)
  max_height = max(heights)

  new_im = Image.new('RGB', (total_width, max_height))

  x_offset = 0
  for im in images:
    new_im.paste(im, (x_offset,0))
    x_offset += im.size[0]

  new_im.save('static/cards/' + card_id + '.png')
  return card_id

@app.route("/")
def main():
  if request.args.get('id') != None:
    dashboard = is_valid_dashboard(request.args.get('id'))
    if dashboard != None:
      return render_template('index.html',accolloformdashboard=True, accolloform=False, dashboard=dashboard)
  else:
    return render_template('index.html', accolloform=True)

@app.route("/create")
def create():
  return render_template('index.html', accolloform=True)

@app.route("/delete")
def delete():
  client = MongoClient()
  client = MongoClient('localhost', 27017)
  db = client['cartediaccollo']
  collection = db['carte']
  data = base64.b64decode(request.args.get('token'))
  data_split = data.split(':')
  dashboard_id = data_split[0]
  token = data_split[1]  
  myquery = { "uuid": request.args.get('id'), "dashboard_id": dashboard_id }
  print "Deleted card: " + str(collection.delete_one(myquery))
  return redirect('/dashboard_accolli?token=' + request.args.get('token'), code=302)

@app.route("/dashboard_accolli")
def dashboard_accolli():
  
  authenticated_dashboard = None
  accolli = {}

  if 'Authorization' in request.headers:
    print("client has Header Authorization: " + request.args.get('token'))
    authorization_header = request.headers['Authorization']
    data = base64.b64decode(authorization_header)
    dashboard_split_array = data.split(':')
    dashboard_id = dashboard_split_array[0]
    token = dashboard_split_array[1]
    authenticated_dashboard = check_valid_authorization(dashboard_id,token)

  elif request.args.get('token') != None:
    print("client has token: " + request.args.get('token'))
    data = base64.b64decode(request.args.get('token'))
    print data
    dashboard_split_array = data.split(':')
    dashboard_id = dashboard_split_array[0]
    token = dashboard_split_array[1]
    print('dashboard id: ' + dashboard_id + ' - token: ' +  token)
    authenticated_dashboard = check_valid_authorization(dashboard_id,token)

  if authenticated_dashboard != None:
    print "User authenticated whith uuid " + authenticated_dashboard['uuid']
    accolli = find_accolli_for_dashboard(authenticated_dashboard['uuid'])
    return render_template('dashboard_accolli.html', token=request.args.get('token'), alert=False, id=dashboard_id, dashboard_name=authenticated_dashboard['name'], accolli=accolli) 
  else:
    return render_template('dashboard_accolli.html', view_form=True, dashboard_name='', accolli = accolli)

@app.route("/dashboard_accolli/create", methods = ['POST', 'GET'])
def create_dashboard_accolli():
  result = request.form
  if ((len(result['nome_dashboard']) < 1) or (len(result['nome_dashboard']) > 30)):
    return redirect(url_for('dashboard_accolli', input_alert=1))

  dashboard = generate_dashboard_id_and_token(result['nome_dashboard'])
  return redirect('/dashboard_accolli?token=' + base64.b64encode(dashboard['uuid'] + ':' + dashboard['token']), code=302)

@app.route("/message",methods = ['POST', 'GET'])
def message():
  card_url = "https://accolli.it/show?id=" + request.args.get('id') + "&token=" + request.args.get('token')
  result = request.form
  gmail_user = os.environ['ACCOLLI_MAIL_USER']
  gmail_password = os.environ['ACCOLLI_MAIL_PASSWORD']
  card = read_card_mongo(request.args.get('id'),request.args.get('token'))
  print "Sending email to " + result['email']
  try:
      server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
      server.ehlo()
      server.login(gmail_user, gmail_password)
      sent_from = gmail_user
      to = [result['email']]
      subject = 'Notifica ricezione Carta Di Accollo da ' + card['sender']
      body = 'Gentile utente,\n\nComplimenti hai ricevuto un Carta Di Accollo da ' + card['sender'] +'!\n\n' \
      'Puoi visualizzarla e scaricarla al seguente link:\n\n' + card_url + '\n\n\n\nGrazie,\nAccolli Operation Team'
      email_text = """\
From: %s
To: %s
Subject: %s

%s
      """ % (sent_from, ", ".join(to), subject, body)
      server.sendmail(sent_from, to, email_text)
      server.close()
  except:
      print 'Something went wrong...'

  return redirect(card_url, code=302)

@app.route("/changestatus")
def changestatus():
  card_url = "https://accolli.it/show?id=" + request.args.get('id') + "&token=" + request.args.get('token') 
  change_card_status(request.args.get('id'),request.args.get('status'))
  return redirect(card_url, code=302)

@app.route("/show")
def show():
  card_id = request.args.get('id')
  token = request.args.get('token')
  card = read_card_mongo(card_id,token)
  card_img_url = "https://accolli.it/static/cards/" + card_id + ".png" 
  emailbody = 'Gentile utente,%0A%0AComplimenti hai ricevuto un Carta Di Accollo da ' + card['sender'] +'!%0A%0A' \
  'Puoi visualizzarla e scaricarla al seguente link:%0Ahttps://accolli.it/show?id=' + card_id + '%26token=' \
  + token + '%0A%0A%0A%0AGrazie,%0AAccolli Operation Team'
  if card:
    print("Card Image URL: " + card_img_url)
    if card['status'] == 'open':
      card_status_desc = 'Questo accollo deve ancora essere completato!'
      text = 'text-primary'
    elif card['status'] == 'progress':
      card_status_desc = 'Ci sto lavorando abbi fede!'
      text = 'text-danger'
    elif card['status'] == 'done':
      card_status_desc = 'Accollo completato!'
      text = 'text-success'
    else:
      card_stauts_desc = 'uhm... stato accollo indefinito.'

    return render_template('show.html',card_img_url = card_img_url, card_status_desc = card_status_desc, text = text, emailbody = emailbody)
  elif card == False:
    return render_template('access_denied.html')

@app.route('/cartadiaccollo',methods = ['POST', 'GET'])
def cartadiaccollo():
  if request.method == 'POST':
    if request.args.get('to') == 'dashboard':
      result = request.form
      inputs = ["sender","task"]
      for _input in inputs:
        if ((len(result[_input]) < 1) or (len(result[_input]) > 60)):
          return render_template('index.html', accolloformdashboard=True, alert=True, accolloform=True)
      
      token = randomString(20)
      print("Foo " + request.args.get('dashboard_id'))
      card_id = create_card_img(str(uuid.uuid1()),request.args.get('dashboard_name'),result['task'],result['sender'],token)
      card_url = "https://accolli.it/show?id=" + card_id + "&token=" + token 
      write_card_mongo(card_id,token,card_url,result['sender'],request.args.get('dashboard_id'))
      return redirect(card_url, code=302)

    else:
      result = request.form
      inputs = ["recipient","sender","task"]
      for _input in inputs:
        if ((len(result[_input]) < 1) or (len(result[_input]) > 60)):
          return render_template('index.html', alert=True, accolloform=True)

      token = randomString(20)
      card_id = create_card_img(str(uuid.uuid1()),result['recipient'],result['task'],result['sender'],token)
      card_url = "https://accolli.it/show?id=" + card_id + "&token=" + token 
      print card_url
      write_card_mongo(card_id,token,card_url,result['sender'],None)
      #return send_file('static/cards/' + card_id + '.png', mimetype='image/png', attachment_filename='CartaDiAccollo.png')
      card_url = "https://accolli.it/show?id=" + card_id + "&token=" + token
      return redirect(card_url, code=302)
  else:
    return redirect('https://accolli.it',code=302) 

if __name__ == "__main__":
    app.run(host='0.0.0.0')
