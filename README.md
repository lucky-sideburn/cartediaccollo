# accolli.it

## Description

This is the repo of [accolli.it](https://accolli.it). It has been written with Flask.

## How to run accoll.it locally

1. Install MongoDB with the following collections:
  * cards
  * dashboards
  * users

2. Build docker image using the Dockerfile or pull docker.io/luckysideburn/cartediaccollo:latest

3. Start Docker

```
docker run -p 5000:5000 -d --env MONGO_HOST=<mongodb_ip_address> -v $PWD/cards:/usr/src/app/static/cards docker.io/luckysideburn/cartediaccollo:latest
```