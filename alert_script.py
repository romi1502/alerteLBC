
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
import yaml


from Crypto.Cipher import AES
import pycurl
import certifi
from bs4 import BeautifulSoup

ads_config_file = "config.json"
email_config_file = "email_config.json"

# BLOCK_SIZE = 32
# PADDING = '{'
# pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING
# DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(PADDING)


def load_config(config_file):
    with open(config_file,'r') as f:
        config = yaml.load(f)

    return config

def load_ads_db(db_file=None):
    """
        load already seen ads from file
    """
    known_ads = set()
    if os.path.exists(db_file):
        with open(db_file, 'r') as f:
            r = csv.reader(f,delimiter='\t')
            for row in r:
                known_ads.add(Ad(*row))
    return known_ads

def update_ads_db(new_ads, db_file=None):
    """
        update db with new adds
    """
    with open(db_file,'a') as f:
        for ad in new_ads:
            f.write("%s\t%s\t%s\t%s\n" %(ad.detail, ad.price, ad.placement, ad.link))

def check_mail_server(sender=None, password='', smtp_url='smtp.gmail.com', smtp_port=587, **unusedkwargs):

    print "Try connection to SMTP server"
    server = smtplib.SMTP(smtp_url, smtp_port) #port 465 or 587
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(sender, password)
    server.quit()
    server.close()

def send_mail(new_ads, config, list_recipients=[], sender=None, password='', smtp_url='smtp.gmail.com', smtp_port=587):
    # current_hash = new_hash
    print "New content, send message"

    # Create a text/plain message
    # msg = MIMEText(body)
    msg = MIMEMultipart('alternative')

    msg['Subject'] = 'Nouvelle annonce %s' % config["title"]
    msg['From'] = sender
    msg['To'] = ', '.join(list_recipients)

    text = config["reference_url"]
    html = "<p>Nouvelles annonces:\n</p>"

    for ad in new_ads:
        html+="<p><a href=%s>%s: %s (%s)</a></p>\n" % (ad.link, ad.detail, ad.price, ad.placement)

    html+= "<br><p>Page monitoree: <a href=%s>%s</a></p>\n" %(config["reference_url"],config["reference_url"])

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

    server = smtplib.SMTP(smtp_url, smtp_port) #port 465 or 587
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(sender, password)
    server.sendmail(sender, list_recipients,msg.as_string())
    server.quit()
    server.close()

def retrieve_ad_list(url, location_filter):
    print "Retrieve URL"
    buff = StringIO()

    c = pycurl.Curl()
    c.setopt(c.URL, url)

    c.setopt(pycurl.CAINFO, certifi.where())

    c.setopt(c.WRITEDATA, buff)
    c.perform()
    c.close()


    body = buff.getvalue()

    parsed_body = BeautifulSoup(body)

    # raw_ad_list = parsed_body.body.find_all('a', attrs={'class':'list_item clearfix trackable'})
    
    script_list = parsed_body.body.find_all('script')
    data_dict = yaml.load(script_list[3].contents[0][20:])

    raw_ad_list = data_dict["adSearch"]["data"].get("ads",[])
    ad_list = []
    for el in raw_ad_list:

        link = el["url"]
        print link
        
        price = str(el.get("price",[-1])[0])

        location = el["location"]["city"]
        if location_filter and (not location in location_filter):
            continue

        #detail = item_info.find('h2', attrs={'class':'item_title'}).getText().replace('\n','').replace('  ','')
        detail = el["subject"]
        detail = detail.encode('ascii','ignore').replace('\t','')
        price = price.encode('ascii','ignore').replace('\t','')
        placement = location.encode('ascii','ignore').replace('\t','')

        ad_list.append(Ad(detail, price, placement, link))


    return ad_list

class Ad(object):

    def __init__(self, detail, price, placement, link):
        self.detail = detail
        self.price = price
        self.placement = placement
        self.link = link

    def __hash__(self):
        return hash(self.detail+self.price+self.placement+self.link)

    def __eq__(self, ad):
        return hash(ad) == hash(self)

if __name__=="__main__":

    ads_config = load_config(ads_config_file)
    email_config = load_config(email_config_file)

    # pwd_filename = os.path.join(os.path.expanduser("~"),'.lbcpassword')

    if not "password" in email_config:
        pwd = getpass.getpass(prompt="Type password for %s"%email_config["sender"])
        email_config["password"] = pwd


    known_ads = []
    for ad_config in ads_config:
        db_file = ad_config["title"].replace(" ","_")+".db"
        known_ads.append(load_ads_db(db_file))


    try:

        # check that credential are working to connect to smtp server.
        check_mail_server(**email_config)

        while True:

            dt = datetime.datetime.now()

            # do nothing between 0am and 6am
            if dt.hour<6:
                print "No check at that time. Waiting 30min"
                time.sleep(1800)
            else:


                for k,ad_config in enumerate(ads_config):


                    ad_list = retrieve_ad_list(ad_config["reference_url"], ad_config.get("location_filter",None))

                    new_ads = []

                    for ad in ad_list:
                        if ad not in known_ads[k]:
                            known_ads[k].add(ad)
                            new_ads.append(ad)

                    if new_ads:
                        db_file = ad_config["title"].replace(" ","_")+".db"
                        update_ads_db(new_ads, db_file=db_file)
                        send_mail(new_ads, ad_config, **email_config)
                    
                wait_time = random.randint(300, 600)
                print "Wait %ds" % wait_time
                time.sleep(wait_time)

    except ValueError as inst:
        cipher=[]
        print inst
