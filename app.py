# coding=utf-8 
from PIL import Image as PILImage
from PIL import ImageEnhance as PILImageEnhance
from PIL import ImageDraw as PILImageDraw
from PIL import ImageFont as PILImageFont

from flask import Flask, render_template, request, send_file, redirect, url_for, Response, session
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
from flask_appbuilder import Model
import base64
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_pymongo import PyMongo
import bcrypt
from flask_avatars import Avatars

app = Flask(__name__)
app.config['MONGO_DBNAME'] = 'cartediaccollo'
app.config['MONGO_URI'] = 'mongodb://' + os.environ['MONGO_HOST'] + ':27017/cartediaccollo'
app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']
avatars = Avatars(app)

mongo = PyMongo(app)
client = MongoClient()
client = MongoClient(os.environ['MONGO_HOST'], 27017)

class User(UserMixin):
    def __init__(self , username , password , id , active=True):
        self.id = id
        self.username = username
        self.password = password
        self.active = active

    def get_id(self):
        return self.id

    def is_active(self):
        return self.active

    def get_auth_token(self):
        return make_secure_token(self.username , key='secret_key')

class UsersRepository:
    def __init__(self):
        self.users = dict()
        self.users_id_dict = dict()
        self.identifier = 0
    
    def save_user(self, user):
        self.users_id_dict.setdefault(user.id, user)
        self.users.setdefault(user.username, user)
    
    def get_user(self, username):
        return self.users.get(username)
    
    def get_user_by_id(self, userid):
        return self.users_id_dict.get(userid)
    
    def next_index(self):
        self.identifier +=1
        return self.identifier

users_repository = UsersRepository()

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
  dashboard = collection.find_one({"name": dashboard_id})
  if dashboard != None:
    return dashboard 
  else:
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
  db = client['cartediaccollo']
  collection = db['carte']
  card = collection.find_one({"uuid": uuid})
  print(card)
  if token != card['token']:
    return False
  else:
    return card

def write_card_mongo(card_id,token,card_url,sender,dashboard_id,task,lightcard=False):
  db = client['cartediaccollo']
  collection = db['carte']
  post = {"uuid": card_id, "token": token, "status": "open", "url": card_url, "sender": sender, "dashboard_id": dashboard_id, "task": task, "lightcard": lightcard}
  post_id = collection.insert_one(post).inserted_id
  print(post_id)

def change_card_status(card_id,new_status):
  db = client['cartediaccollo']
  collection = db['carte']
  myquery = { "uuid": card_id }
  newvalues = { "$set": { "status": new_status } }
  return collection.update_one(myquery, newvalues)

def create_card_img(card_id,recipient,task,sender,token,lightcard=False,card_color='black'):
  img = PILImage.new('RGB', (1024, 800), color = card_color)
  d = PILImageDraw.Draw(img)
  task = task.replace("<br>", "\n")

  fill_color = 'white'

  if card_color == 'orange':
    fill_color = 'black'

 
  if lightcard:
    font = PILImageFont.truetype("Inconsolata-Regular.ttf",70)
    card_text = task

  else:
    font = PILImageFont.truetype("Inconsolata-Regular.ttf",28)
    card_text = "Gentile " + recipient + ",\n\n\nLa presente Carta Di Accollo creata in data " + time.strftime("%d/%m/%Y") + \
    "\ncertifica che ho preso in considerazione la tua richiesta.\n\n" \
    "Io sottoscritto/a, " + sender + ", mi impegno ad occuparmi di:\n" + task + ".\n\n" \
    "Per favore non chiedermi troppo spesso feedback sullo stato\ndi completamento! Ci sto lavorando!\n\n"
    
  d.text((100,100), card_text, fill=fill_color, font=font)
  
  font = PILImageFont.truetype("Inconsolata-Regular.ttf",24)
  details = "ID: " + card_id + "\n" \
  "Token: " + token + "\n" \
  "Scansiona il QR code per accedere alla richiesta" \
  "\n\n\n\n" + "Crea anche tu accolli certificati su https://accolli.it" 
  d.text((100,500), details, fill=fill_color,font=font)
  
  img.save('static/cards/' + card_id + '-text.png')
  
  qr = qrcode.QRCode(
      version=1,
      error_correction=qrcode.constants.ERROR_CORRECT_L,
      box_size=6,
      border=1,
  )

  qr_data = "https://accolli.it/show?id=" + card_id + "&token=" + token  
  print(qr_data)
  qr.add_data(qr_data)
  qr.make(fit=True)


  img = qr.make_image(fill_color=fill_color, back_color=card_color)
  img.save('static/cards/' + card_id + '-qr.png')

  images = [PILImage.open(x) for x in ['static/cards/' + card_id + '-text.png', 'static/cards/' + card_id + '-qr.png']]
  widths, heights = zip(*(i.size for i in images))
  total_width = sum(widths)
  max_height = max(heights)

  new_im = PILImage.new('RGB', (total_width, max_height), color = card_color)

  x_offset = 0
  for im in images:
    new_im.paste(im, (x_offset,0))
    x_offset += im.size[0]

  new_im.save('static/cards/' + card_id + '.png', format="png")
  im = PILImage.open('static/cards/' + card_id + '.png')
  enhancer = PILImageEnhance.Brightness(im)
  enhanced_im = enhancer.enhance(0.9)
  enhanced_im.save('static/cards/' + card_id + '.png', format="png")

  return card_id

@app.route("/")
def main():
  if 'username' in session:
      print('You are logged in as ' + session['username'])

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
  db = client['cartediaccollo']
  collection = db['carte']
  myquery = { "uuid": request.args.get('id'), "dashboard_id": session['username']}
  print("Deleted card: " + str(collection.delete_one(myquery)))
  return redirect('/dashboard_accolli', code=302)

@app.route("/dashboard_accolli")
def dashboard_accolli():
  
  authenticated_dashboard = None
  accolli = {}

  if session['username']:
    accolli = find_accolli_for_dashboard(session['username'])
    return render_template('dashboard_accolli.html', alert=False, id=session['username'], dashboard_name=session['username'], accolli=reversed(accolli)) 
  else:
    return render_template('dashboard_accolli.html', view_form=True, dashboard_name='', accolli = reversed(accolli))

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
  print("Sending email to " + result['email'])
  try:
      server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
      server.ehlo()
      server.login(gmail_user, gmail_password)
      sent_from = gmail_user
      to = [result['email']]
      subject = 'Notifica ricezione Carta Di Accollo da ' + card['sender']
      body = 'Gentile utente,\n\nComplimenti hai ricevuto un Carta Di Accollo da ' + card['sender'] +'!\n\n' \
      'Puoi visualizzarla e scaricarla al seguente link:\n\n' + card_url + '\n\nGrazie,\nAccolli Operation Team'
      email_text = """\
From: %s
To: %s
Subject: %s

%s
      """ % (sent_from, ", ".join(to), subject, body)
      server.sendmail(sent_from, to, email_text)
      server.close()
  except:
      print('Something went wrong...')

  return redirect(card_url, code=302)

@app.route("/changestatus")
def changestatus():
  card_url = "https://accolli.it/show?id=" + request.args.get('id') + "&token=" + request.args.get('token') 
  change_card_status(request.args.get('id'),request.args.get('status'))
  card = read_card_mongo(request.args.get('id'), request.args.get('token'))
  return redirect(card_url + '&status=' + request.args.get('status') + '&sender=' + card['sender'], code=302)

@app.route("/show")
def show():

  if request.args.get('id') == "9d32a088-2ba9-11ea-b25c-38f9d358ebff":
    return redirect('https://accolli.it?qr_how_to=true', code=302)

  if request.args.get('token') == None:
    return render_template('access_denied.html')

  card_id = request.args.get('id')
  token = request.args.get('token')
  card = read_card_mongo(card_id,token)
  card_img_url = "https://accolli.it/static/cards/" + card_id + ".png" 
  emailbody = 'Gentile Utente,%0A%0AComplimenti hai ricevuto una Carta Di Accollo da ' + card['sender'] +'!%0A%0A' \
  'Puoi visualizzarla e scaricarla al seguente link:%0Ahttps://accolli.it/show?id=' + card_id + '%26token=' \
  + token + '%0A%0A%0AGrazie,%0AAccolli Operation Team'
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

    if not 'lightcard' in card.keys():
      card['lightcard'] = False

    return render_template('show.html',card_img_url = card_img_url, card_status_desc = card_status_desc, text = text, emailbody = emailbody, lightcard = card['lightcard'])
  elif card == False:
    return render_template('access_denied.html')

@app.route('/cartadiaccollo',methods = ['POST', 'GET'])
def cartadiaccollo():
  if request.method == 'POST':
    print(str(request.form))
    result = request.form
    inputs = ["recipient","sender","task"]
    if request.args.get('to') == 'dashboard':
      token = randomString(20)

      if result['external_sender'] == 'true':
        return_url = 'https://accolli.it/?id=' + result['recipient'] + '&alert=true'      
      elif session['username'] == result['recipient']:
        return_url = '/dashboard_accolli?&alert=true'

      for _input in inputs:
        if (len(result[_input]) < 2):
          return redirect(return_url, code=302)
      if ((len(result['sender']) > 30) or (len(result['recipient']) > 30)):
        return redirect(return_url, code=302)
      elif (len(result['task']) > 60):
        return redirect(return_url, code=302)

      if request.args.get('autoaccollo') == "yes":
        sender = result['dashboard_name']
        print("Foo " + request.args.get('dashboard_id'))

      else:
        sender = result['sender']

      if 'lightcard' in result.keys():
        lightcard = True
      else:
        lightcard = False

      card_id = create_card_img(str(uuid.uuid1()), sender, result['task'], request.args.get('dashboard_name'), token, lightcard, result['color'])
      card_url = "https://accolli.it/show?id=" + card_id + "&token=" + token 
      write_card_mongo(card_id,token, card_url, request.args.get('dashboard_id'), request.args.get('dashboard_id'), result['task'], lightcard)

      if session and (result['recipient'] == session['username'] and request.args.get('dashboard_name') == session['username']):
        return redirect('/dashboard_accolli', code=302)
      else:
        return redirect(card_url, code=302)

    else:
      for _input in inputs:
        if (len(result[_input]) < 2):
          return render_template('index.html', alert=True, accolloform=True)
      if ((len(result['sender']) > 30) or (len(result['recipient']) > 30)):
        return render_template('index.html', alert=True, accolloform=True)
      elif (len(result['task']) > 60):
        return render_template('index.html', alert=True, accolloform=True)

      token = randomString(20)
      card_id = create_card_img(str(uuid.uuid1()),result['recipient'],result['task'],result['sender'],token, False, result['color'])
      card_url = "https://accolli.it/show?id=" + card_id + "&token=" + token 
      print(card_url)
      write_card_mongo(card_id,token,card_url,result['sender'], None, result['task'])
      #return send_file('static/cards/' + card_id + '.png', mimetype='image/png', attachment_filename='CartaDiAccollo.png')
      card_url = "https://accolli.it/show?id=" + card_id + "&token=" + token
      return redirect(card_url, code=302)
  else:
    return redirect('https://accolli.it',code=302) 

@app.route('/logout')
def logout():
   print("Logout " + session['username'])
   session.pop('username', None)
   return redirect(url_for('main'))

@app.route('/login', methods=['POST'])
def login():
    users = mongo.db.users
    login_user = users.find_one({'name' : request.form['username']})
    if login_user:
        if bcrypt.hashpw(request.form['pass'].encode('utf-8'), login_user['password']) == login_user['password']:
            session['username'] = request.form['username']
            return redirect(url_for('dashboard_accolli'))

    return render_template('index.html', accolloform=True, invalid_credential=True)

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        users = mongo.db.users
        existing_user = users.find_one({'name' : request.form['username']})

        if existing_user is None:
            hashpass = bcrypt.hashpw(request.form['pass'].encode('utf-8'), bcrypt.gensalt())
            users.insert({'name' : request.form['username'], 'password' : hashpass})
            session['username'] = request.form['username']
            dashboard = generate_dashboard_id_and_token(request.form['username'])
            token = randomString(20)
            card_id = create_card_img(str(uuid.uuid1()), request.form['username'], 'inviarti accollo di benvenuto!', 'accolli.it', token, False, 'black')
            card_url = "https://accolli.it/show?id=" + card_id + "&token=" + token 
            write_card_mongo(card_id,token, card_url, 'accolli.it', request.form['username'], 'inviarti accollo di benvenuto!')
            return redirect(url_for('main'))

        return render_template('index.html', accolloform=True, user_already_exists=True)

    return render_template('register.html')

@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

if __name__ == "__main__":
    app.run(host='0.0.0.0')

