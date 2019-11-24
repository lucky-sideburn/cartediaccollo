# coding=utf-8
from PIL import ImageFont, Image, ImageDraw
from flask import Flask, render_template, request, send_file, redirect
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

app = Flask(__name__)

def randomString(stringLength=10):
    """Generate a random string of fixed length """
    lettersAndDigits = string.ascii_lowercase + string.digits
    return ''.join(random.choice(lettersAndDigits) for i in range(stringLength))

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

def write_card_mongo(card_id,token,card_url):
  client = MongoClient()
  client = MongoClient('localhost', 27017)
  db = client['cartediaccollo']
  collection = db['carte']
  post = {"uuid": card_id, "token": token, "status": "open", "url": card_url}
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


def create_card_img(recipient,task,sender,token):
  card_id = str(uuid.uuid1())
  img = Image.new('RGB', (1024, 800), color = (0, 0, 0))
  d = ImageDraw.Draw(img)
  
  font = ImageFont.truetype("Inconsolata-Regular.ttf",28)
  card_text = "Gentile " + recipient + ",\n\n\nLa presente Carta Di Accollo creata in data " + time.strftime("%d/%m/%Y") + \
  "\ncertifica che ho preso in considerazione la tua richiesta.\n\n" \
  "Io sottoscritto, " + sender + ", mi impegno ad occuparmi di " + task + ".\n\n" \
  "Per favore non chiedermi troppo spesso feedback sullo stato\ndi completamento! Ci sto lavorando!\n\n"
  d.text((100,100), card_text, fill=(255,255,255),font=font)
  
  font = ImageFont.truetype("Inconsolata-Regular.ttf",24)
  details = "ID: " + card_id + "\n" \
  "Token: " + token + "\n" \
  "Scansiona il QR code per accedere alla della richiesta" \
  "\n\n\n\n" + "Crea anche tu accolli certificati su http://accollicertificati.org" 
  d.text((100,500), details, fill=(255,255,255),font=font)
  
  img.save('static/cards/' + card_id + '-text.png')
  
  qr = qrcode.QRCode(
      version=1,
      error_correction=qrcode.constants.ERROR_CORRECT_L,
      box_size=6,
      border=1,
  )

  qr_data = "http://accollicertificati.org:5000/show?id=" + card_id + "&token=" + token  
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
    return render_template('index.html')

@app.route("/message",methods = ['POST', 'GET'])
def message():
  card_url = "http://accollicertificati.org:5000/show?id=" + request.args.get('id') + "&token=" + request.args.get('token')
  result = request.form
  gmail_user = 'accollicertificati@gmail.com'
  gmail_password = 'accollo.123!!'
  print "Sending email to " + result['email']
  try:
      server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
      server.ehlo()
      server.login(gmail_user, gmail_password)
      sent_from = gmail_user
      to = [result['email']]
      subject = 'Notifica ricezione Carta Di Accollo'
      body = 'Gentile utente,\n\nComplimenti hai ricevuto un Carta Di Accollo!\n\n' \
      'La puoi trovare allegata con la presente e-mail o puoi visualizzarla al seguente link:\n\n' + card_url + '\n\n\n\nGrazie,\nAccolli Operation Team'
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
  card_url = "http://accollicertificati.org:5000/show?id=" + request.args.get('id') + "&token=" + request.args.get('token') 
  change_card_status(request.args.get('id'),request.args.get('status'))
  return redirect(card_url, code=302)

@app.route("/show")
def show():
    card_id = request.args.get('id')
    token = request.args.get('token')
    card = read_card_mongo(card_id,token)
    card_img_url = "http://accollicertificati.org:5000/static/cards/" + card_id + ".png" 
    if card:
      print("Card Image URL: " + card_img_url)
      if card['status'] == 'open':
        card_status_desc = 'Questo accollo devo ancora essere completato!'
        text = 'text-primary'
      elif card['status'] == 'progress':
        card_status_desc = 'Ci sto lavorando abbi fede!'
        text = 'text-danger'
      elif card['status'] == 'done':
        card_status_desc = 'Accollo completato!'
        text = 'text-success'
      else:
        card_stauts_desc = 'uhm... stato accollo indefinito.'

      return render_template('show.html',card_img_url = card_img_url, card_status_desc = card_status_desc, text = text)
    elif card == False:
      return render_template('access_denied.html')

@app.route('/cartadiaccollo',methods = ['POST', 'GET'])
def cartadiaccollo():
   if request.method == 'POST':
      result = request.form

      inputs = ["recipient","sender","task"]

      for _input in inputs:
        if ((len(result[_input]) < 1) or (len(result[_input]) > 60)):
          return render_template('index.html', alert=True)

      token = randomString(20)
      card_id = create_card_img(result['recipient'],result['task'],result['sender'],token)
      card_url = "http://accollicertificati.org:5000/show?id=" + card_id + "&token=" + token 
      print card_url
      write_card_mongo(card_id,token,card_url)
      #return send_file('static/cards/' + card_id + '.png', mimetype='image/png', attachment_filename='CartaDiAccollo.png')
      card_url = "http://accollicertificati.org:5000/show?id=" + card_id + "&token=" + token
      return redirect(card_url, code=302)


if __name__ == "__main__":
    app.run()
