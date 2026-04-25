# coding=utf-8
import os
import uuid
import time
import string
import random
import smtplib

from PIL import Image as PILImage, ImageEnhance as PILImageEnhance, ImageDraw as PILImageDraw, ImageFont as PILImageFont
from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from flask_pymongo import PyMongo
from flask_avatars import Avatars
import qrcode
import bcrypt

app = Flask(__name__)
base_url = os.environ['BASE_URL']
app.config['MONGO_DBNAME'] = 'cartediaccollo'
app.config['MONGO_URI'] = 'mongodb://' + os.environ['MONGO_HOST'] + ':27017/cartediaccollo'
app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']

avatars = Avatars(app)
mongo = PyMongo(app)

_client = MongoClient(os.environ['MONGO_HOST'], 27017, ssl=False)
db = _client['cartediaccollo']

os.makedirs('static/cards', exist_ok=True)

STATUS_DESCRIPTIONS = {
    'open':    ('Questo accollo deve ancora essere completato!', 'text-primary'),
    'progress': ('Ci sto lavorando abbi fede!', 'text-danger'),
    'done':    ('Accollo completato!', 'text-success'),
    'deleted': ('Accollo cancellato!', 'text-info'),
}


def random_token(length=10):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def find_accolli_for_dashboard(dashboard_id):
    return list(db['carte'].find({"dashboard_id": dashboard_id, "status": {"$ne": "deleted"}}))


def is_valid_dashboard(dashboard_id):
    return db['dashboards'].find_one({"name": dashboard_id})


def generate_dashboard_id_and_token(name):
    collection = db['dashboards']
    dashboard_id = str(uuid.uuid4())
    while collection.find_one({"uuid": dashboard_id}):
        dashboard_id = str(uuid.uuid4())
    dashboard = {"uuid": dashboard_id, "token": random_token(20), "name": name}
    result = collection.insert_one(dashboard)
    return dashboard if result.inserted_id else None


def read_card_mongo(card_uuid, token):
    card = db['carte'].find_one({"uuid": card_uuid})
    if card is None or card.get('token') != token:
        return None
    return card


def write_card_mongo(card_id, token, card_url, sender, dashboard_id, task, lightcard=False):
    db['carte'].insert_one({
        "uuid": card_id,
        "token": token,
        "status": "open",
        "url": card_url,
        "sender": sender,
        "dashboard_id": dashboard_id,
        "task": task,
        "lightcard": lightcard,
    })


def change_card_status(card_id, new_status):
    db['carte'].update_one({"uuid": card_id}, {"$set": {"status": new_status}})


def create_card_img(card_id, recipient, task, sender, token, lightcard=False, card_color='black'):
    fill_color = 'black' if card_color == 'orange' else 'white'
    task_text = task.replace("<br>", "\n")

    img = PILImage.new('RGB', (1024, 800), color=card_color)
    d = PILImageDraw.Draw(img)

    if lightcard:
        font = PILImageFont.truetype("Inconsolata-Regular.ttf", 70)
        card_text = task_text
    else:
        font = PILImageFont.truetype("Inconsolata-Regular.ttf", 28)
        card_text = (
            f"Gentile {recipient},\n\n\n"
            f"La presente Carta Di Accollo creata in data {time.strftime('%d/%m/%Y')}\n"
            "certifica che ho preso in considerazione la tua richiesta.\n\n"
            f"Io sottoscritto/a, {sender}, mi impegno ad occuparmi di:\n{task_text}.\n\n"
            "Per favore non chiedermi troppo spesso feedback sullo stato\n"
            "di completamento! Ci sto lavorando!\n\n"
        )

    d.text((100, 100), card_text, fill=fill_color, font=font)

    details_font = PILImageFont.truetype("Inconsolata-Regular.ttf", 24)
    if lightcard:
        details = (
            f"ID: {card_id}\n"
            f"Token: {token}\n"
            f"Creata da: {sender}\n"
            "Scansiona il QR code per visualizzare questa carta di accollo"
            f"\n\nCrea anche tu accolli certificati su {base_url}"
        )
    else:
        details = (
            f"ID: {card_id}\n"
            f"Token: {token}\n"
            "Scansiona il QR code per accedere alla richiesta"
            f"\n\n\n\nCrea anche tu accolli certificati su {base_url}"
        )
    d.text((100, 500), details, fill=fill_color, font=details_font)

    text_path = f'static/cards/{card_id}-text.png'
    qr_path = f'static/cards/{card_id}-qr.png'
    final_path = f'static/cards/{card_id}.png'

    img.save(text_path)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=1,
    )
    qr.add_data(f"{base_url}/show?id={card_id}&token={token}")
    qr.make(fit=True)
    qr.make_image(fill_color=fill_color, back_color=card_color).save(qr_path)

    images = [PILImage.open(p) for p in [text_path, qr_path]]
    widths, heights = zip(*(i.size for i in images))
    combined = PILImage.new('RGB', (sum(widths), max(heights)), color=card_color)
    x = 0
    for im in images:
        combined.paste(im, (x, 0))
        x += im.size[0]

    PILImageEnhance.Brightness(combined).enhance(0.9).save(final_path, format="png")

    os.remove(text_path)

    return card_id


def _validate_card_inputs(result):
    for field in ['recipient', 'sender', 'task']:
        if len(result.get(field, '')) < 2:
            return False
    if len(result.get('sender', '')) > 30 or len(result.get('recipient', '')) > 30:
        return False
    if len(result.get('task', '')) > 60:
        return False
    return True


@app.route("/")
def main():
    dashboard_id = request.args.get('id')
    if dashboard_id:
        dashboard = is_valid_dashboard(dashboard_id)
        if dashboard:
            return render_template('index.html', accolloformdashboard=True, accolloform=False,
                                   dashboard=dashboard, base_url=base_url)
    return render_template('index.html', accolloform=True, base_url=base_url)


@app.route("/create")
def create():
    return render_template('index.html', accolloform=True, base_url=base_url)


@app.route("/delete")
def delete():
    db['carte'].update_one(
        {"uuid": request.args.get('id'), "dashboard_id": session.get('username')},
        {"$set": {"status": "deleted"}}
    )
    return redirect('/dashboard_accolli', code=302)


@app.route("/dashboard_accolli")
def dashboard_accolli():
    if 'username' not in session:
        return redirect('/', code=302)
    username = session['username']
    accolli = find_accolli_for_dashboard(username)
    return render_template('dashboard_accolli.html',
                           id=username,
                           dashboard_name=username,
                           accolli=list(reversed(accolli)),
                           base_url=base_url)


@app.route("/dashboard_accolli/create", methods=['POST'])
def create_dashboard_accolli():
    name = request.form.get('nome_dashboard', '')
    if not (1 < len(name) <= 30):
        return redirect(url_for('dashboard_accolli', input_alert=1))
    generate_dashboard_id_and_token(name)
    return redirect('/dashboard_accolli', code=302)


@app.route("/message", methods=['POST', 'GET'])
def message():
    card_id = request.args.get('id')
    token = request.args.get('token')
    card_url = f"{base_url}/show?id={card_id}&token={token}"
    card = read_card_mongo(card_id, token)
    if not card:
        return redirect('/', code=302)

    gmail_user = os.environ.get('ACCOLLI_MAIL_USER', '')
    gmail_password = os.environ.get('ACCOLLI_MAIL_PASSWORD', '')
    recipient_email = request.form.get('email', '')

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(gmail_user, gmail_password)
        subject = f"Notifica ricezione Carta Di Accollo da {card['sender']}"
        body = (
            f"Gentile utente,\n\nComplimenti hai ricevuto una Carta Di Accollo da {card['sender']}!\n\n"
            f"Puoi visualizzarla e scaricarla al seguente link:\n\n{card_url}\n\n"
            "Grazie,\nAccolli Operation Team"
        )
        email_text = f"From: {gmail_user}\nTo: {recipient_email}\nSubject: {subject}\n\n{body}"
        server.sendmail(gmail_user, [recipient_email], email_text)
        server.close()
    except Exception as e:
        app.logger.error(f"Email send failed: {e}")

    return redirect(card_url, code=302)


@app.route("/stats")
def stats():
    total_cards = db['carte'].count_documents({})
    total_users = mongo.db.users.count_documents({})

    by_status = {
        'open':     db['carte'].count_documents({"status": "open"}),
        'progress': db['carte'].count_documents({"status": "progress"}),
        'done':     db['carte'].count_documents({"status": "done"}),
        'deleted':  db['carte'].count_documents({"status": "deleted"}),
    }
    lightcards = db['carte'].count_documents({"lightcard": True})
    active = total_cards - by_status['deleted']

    return render_template('stats.html',
                           total_cards=total_cards,
                           total_users=total_users,
                           active=active,
                           by_status=by_status,
                           lightcards=lightcards,
                           base_url=base_url)


@app.route("/changestatus")
def changestatus():
    card_id = request.args.get('id')
    token = request.args.get('token')
    new_status = request.args.get('status')
    change_card_status(card_id, new_status)
    card = read_card_mongo(card_id, token)
    sender = card['sender'] if card else ''
    return redirect(f"{base_url}/show?id={card_id}&token={token}&status={new_status}&sender={sender}", code=302)


@app.route("/show")
def show():
    if request.args.get('id') == "9d32a088-2ba9-11ea-b25c-38f9d358ebff":
        return redirect(f"{base_url}?qr_how_to=true", code=302)

    card_id = request.args.get('id')
    token = request.args.get('token')

    if not token:
        return render_template('access_denied.html')

    card = read_card_mongo(card_id, token)
    if not card:
        return render_template('access_denied.html')

    card_img_url = f"{base_url}/static/cards/{card_id}.png"
    emailbody = (
        f"Gentile Utente,%0A%0AComplimenti hai ricevuto una Carta Di Accollo"
        f" da {card['sender']}!%0A%0A"
        f"Puoi visualizzarla e scaricarla al seguente link:%0A"
        f"{base_url}/show?id={card_id}%26token={token}"
        "%0A%0A%0AGrazie,%0AAccolli Operation Team"
    )

    status = card.get('status', 'open')
    card_status_desc, text = STATUS_DESCRIPTIONS.get(status, ('Stato accollo indefinito.', 'text-secondary'))
    lightcard = card.get('lightcard', False)

    return render_template('show.html',
                           card_img_url=card_img_url,
                           card_status_desc=card_status_desc,
                           text=text,
                           emailbody=emailbody,
                           lightcard=lightcard,
                           base_url=base_url)


@app.route('/cartadiaccollo', methods=['POST'])
def cartadiaccollo():
    result = request.form
    to_dashboard = request.args.get('to') == 'dashboard'

    if to_dashboard:
        if result.get('external_sender') == 'true':
            return_url = f"{base_url}/?id={result.get('recipient', '')}&alert=true"
        else:
            return_url = '/dashboard_accolli?alert=true'

        if not _validate_card_inputs(result):
            return redirect(return_url, code=302)

        token = random_token(20)
        lightcard = 'lightcard' in result
        recipient = result.get('recipient', result.get('sender', ''))
        task = result['task']
        color = result.get('color', 'black')
        dashboard_id = request.args.get('dashboard_id')
        sender = request.args.get('dashboard_name', result.get('sender', ''))

        card_id = create_card_img(str(uuid.uuid1()), recipient, task, sender, token, lightcard, color)
        card_url = f"{base_url}/show?id={card_id}&token={token}"
        write_card_mongo(card_id, token, card_url, dashboard_id, dashboard_id, task, lightcard)

        if session.get('username') and result.get('recipient') == session['username']:
            return redirect('/dashboard_accolli', code=302)
        return redirect(card_url, code=302)

    else:
        if not _validate_card_inputs(result):
            return render_template('index.html', alert=True, accolloform=True, base_url=base_url)

        token = random_token(20)
        recipient = result['recipient']
        task = result['task']
        sender = result['sender']
        color = result.get('color', 'black')

        card_id = create_card_img(str(uuid.uuid1()), recipient, task, sender, token, False, color)
        card_url = f"{base_url}/show?id={card_id}&token={token}"
        write_card_mongo(card_id, token, card_url, sender, None, task)
        return redirect(card_url, code=302)


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('main'))


@app.route('/login', methods=['POST'])
def login():
    users = mongo.db.users
    user = users.find_one({'name': request.form['username']})
    if user and bcrypt.hashpw(request.form['pass'].encode('utf-8'), user['password']) == user['password']:
        session['username'] = request.form['username']
        return redirect(url_for('dashboard_accolli'))
    return render_template('index.html', accolloform=True, invalid_credential=True, base_url=base_url)


@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        users = mongo.db.users
        if users.find_one({'name': request.form['username']}) is not None:
            return render_template('index.html', accolloform=True, user_already_exists=True, base_url=base_url)

        hashpass = bcrypt.hashpw(request.form['pass'].encode('utf-8'), bcrypt.gensalt())
        username = request.form['username']
        users.insert_one({'name': username, 'password': hashpass})
        session['username'] = username
        generate_dashboard_id_and_token(username)

        token = random_token(20)
        card_id = create_card_img(str(uuid.uuid1()), username, 'inviarti accollo di benvenuto!',
                                  'accolli.it', token, False, 'black')
        card_url = f"{base_url}/show?id={card_id}&token={token}"
        write_card_mongo(card_id, token, card_url, 'accolli.it', username, 'inviarti accollo di benvenuto!')
        return redirect(url_for('dashboard_accolli'))

    return render_template('index.html', accolloform=True, base_url=base_url)


@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r


if __name__ == "__main__":
    app.run(host='0.0.0.0')
