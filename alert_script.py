
import getpass
from StringIO import StringIO
import time
import  datetime
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import os
import csv

from Crypto.Cipher import AES
import pycurl
from bs4 import BeautifulSoup

ref_url = 'http://www.leboncoin.fr/electromenager/offres/ile_de_france/?f=a&th=1&pe=9&q=frigo+OR+refrigerateur+OR+frigidaire'#'http://www.leboncoin.fr/electromenager/offres/ile_de_france/?f=a&th=1&pe=11&q=sechante'
title = 'Frigo pas trop cher'
me = 'hennequin.romain@gmail.com'
list_recipients = [me]#,#'caroline.furois@hotmail.fr'
location_filter = {'Paris', 'Val-de-Marne','Hauts-de-Seine'}

save_file = '/Users/rhennequin/Downloads/list_ads'

BLOCK_SIZE = 32
PADDING = '{'
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING
DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(PADDING)


if os.path.exists(save_file):
    known_ads = set()
    with open(save_file,'r') as f:
        r = csv.reader(f,delimiter='\t')
        for row in r:
            known_ads.add(tuple(row))
else:
    known_ads = set()
try:
    with open('/Users/rhennequin/.password','r') as f:
        cipher = AES.new(pad(getpass.getpass(prompt="Encrypting key")))
        pwd = f.read()

    print "Try connection to SMTP server"
    server = smtplib.SMTP('smtp.gmail.com',587) #port 465 or 587
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(me, DecodeAES(cipher, pwd))
    server.quit()
    server.close()

    # current_hash = 0
    while True:

        dt = datetime.datetime.now()

        # do nothing between 0am and 6am
        if dt.hour<6:
            print "No check at that time. Waiting 30min"
            time.sleep(1800)
        else:
            print "Retrieve URL"
            buff = StringIO()

            c = pycurl.Curl()
            c.setopt(c.URL, ref_url)

            c.setopt(c.WRITEDATA, buff)
            c.perform()
            c.close()

            body = buff.getvalue()

            #new_hash = hash(body)

            parsed_body = BeautifulSoup(body)
            ad_list = parsed_body.body.find_all('div', attrs={'class':'lbc'})


            new_ads = []
            for el in ad_list:
                try:
                    price = el.find('div', attrs={'class':'price'}).getText().replace('\n','').replace('  ','')
                except AttributeError:
                    print "Problem while scanning price"
                    price = ''
                placement = el.find('div', attrs={'class':'placement'}).getText().replace('\n','').replace('  ','')
                kept = False
                for location in location_filter:
                    if location in placement:
                        kept = True
                        break

                if not kept:
                    continue

                detail = el.find('h2', attrs={'class':'title'}).getText().replace('\n','').replace('  ','')
                link = el.parent.attrs['href']
                detail = detail.encode('ascii','ignore').replace('\t','')
                price = price.encode('ascii','ignore').replace('\t','')
                placement = placement.encode('ascii','ignore').replace('\t','')

                if (detail,price,placement, link) not in known_ads:
                    known_ads.add((detail, price, placement, link))
                    new_ads.append((detail, price, placement, link))

            with open(save_file,'a') as f:
                for el in new_ads:
                    f.write("%s\t%s\t%s\t%s\n" %(el))


            if new_ads:
                # current_hash = new_hash
                print "New content, send message"

                # Create a text/plain message
                # msg = MIMEText(body)
                msg = MIMEMultipart('alternative')

                msg['Subject'] = 'Nouvelle annonce %s' % title
                msg['From'] = me
                msg['To'] = ', '.join(list_recipients)

                text = ref_url
                html = "<p>Nouvelles annonces:\n</p>"

                for el in new_ads:
                    html+="<p><a href=%s>%s: %s (%s)</a></p>\n" % (el[3],el[0],el[1],el[2])

                html+= "<br><p>Page monitoree: <a href=%s>%s</a></p>\n" %(ref_url,ref_url)

                # html = html.replace('\xa0\u20ac','euros')
                # html = html.replace('\xe9','e')
                # Record the MIME types of both parts - text/plain and text/html.
                part1 = MIMEText(text, 'plain')
                part2 = MIMEText(html.encode('ascii','ignore'), 'html')

                # Attach parts into message container.
                # According to RFC 2046, the last part of a multipart message, in this case
                # the HTML message, is best and preferred.
                msg.attach(part1)
                msg.attach(part2)

                server = smtplib.SMTP('smtp.gmail.com',587) #port 465 or 587
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(me, DecodeAES(cipher, pwd))
                server.sendmail(me,list_recipients,msg.as_string())
                server.quit()
                server.close()


            wait_time = random.randint(600,900)
            print "Wait %ds" % wait_time
            time.sleep(wait_time)
except ValueError as inst: #BaseException
    cipher=[]
    print inst