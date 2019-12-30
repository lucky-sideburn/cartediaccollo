FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

RUN rm -rf static/cards/*

COPY . .

CMD [ "python", "./app.py" ]
