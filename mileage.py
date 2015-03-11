
import requests
import json
import time
import logging
import pygal
import datetime
import boto
from boto.s3.key import Key

from pprint import pformat,pprint
from options import *


def km_to_miles(km):
    return int(float(km) * 0.621371)

def get_current_data_from_ford():

    response = requests.post(ford_url,data=json.dumps(login_data),headers=headers)

    data = response.json()['response']

    to_post = {
        'ELECTRICDTE':km_to_miles(data['ELECTRICDTE']),
        'ODOMETER':km_to_miles(data['ODOMETER']),
        'stateOfCharge':data['stateOfCharge'],
        'private_key':private_key,
        'orig_timestamp':time.time()
    }
    logging.info(to_post)
    return to_post

def push_to_sparkfun(data):
    push_headers = {'Phant-Private-Key': private_key}
    push = requests.get(add_data_url,params=data,headers=push_headers)
    return push

def linreg(X, Y):
    from math import sqrt
    if len(X) != len(Y):  raise ValueError, 'unequal length'

    N = len(X)
    Sx = Sy = Sxx = Syy = Sxy = 0.0
    for x, y in map(None, X, Y):
        Sx = Sx + x
        Sy = Sy + y
        Sxx = Sxx + x*x
        Syy = Syy + y*y
        Sxy = Sxy + x*y
    det = Sxx * N - Sx * Sx
    a, b = (Sxy * N - Sy * Sx)/det, (Sxx * Sy - Sx * Sxy)/det

    meanerror = residual = 0.0
    for x, y in map(None, X, Y):
        meanerror = meanerror + (y - Sy/N)**2
        residual = residual + (y - a * x - b)**2
    RR = 1 - residual/meanerror
    ss = residual / (N-2)
    Var_a, Var_b = ss * N / det, ss * Sxx / det

    # print "y=ax+b"
    # print "N= %d" % N
    # print "a= %g \\pm t_{%d;\\alpha/2} %g" % (a, N-2, sqrt(Var_a))
    # print "b= %g \\pm t_{%d;\\alpha/2} %g" % (b, N-2, sqrt(Var_b))
    # print "R^2= %g" % RR
    # print "s^2= %g" % ss

    return a, b

def predict_linear(X,Y,future_points):
    a,b = linreg(
        X,
        Y
    )
    #print("y = %s * %s + %s" % (a,future_points,b))
    output = (a * future_points) + b
    return output

def get_all_data_from_sparkfun():
    data = requests.get(get_data_url).json()[::-1]
    line_chart = pygal.DateY(
        x_label_rotation=20,
        fill=True,
        human_readable=True,
        pretty_print=True,
        width=800,
        print_values=False,
        disable_xml_declaration=False
    )

    prediction = predict_linear(
        [float(datapoint['orig_timestamp']) for datapoint in data],
        [float(datapoint['ODOMETER']) for datapoint in data],
        (365 * 86400) + time.mktime(datetime.date(2014,6,21).timetuple())
    )
    overage_cost = max(0,int((prediction - 15000) * .20))
    line_chart.title = "odometer over time \n prediction: %s \n overage cost $%s" % (int(prediction),overage_cost)

    dates = []
    for datapoint in data:
        dates.append(
            (
                datetime.datetime.fromtimestamp(float(datapoint['orig_timestamp'])),
                float(datapoint['ODOMETER'])
            )
        )


    #pprint(dates)
    line_chart.add("Odometer",dates)


    return line_chart.render()

def save_to_s3(filename,data):
    s3conn = boto.connect_s3(s3_akia, s3_secret) #set up an S3 style connections
    bucket = s3conn.get_bucket(s3_bucket)
    k = Key(bucket)
    k.key = filename
    k.set_contents_from_string(data)
    k.content_type = 'image/svg+xml'
    return k

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     to_post = get_current_data_from_ford()
#     push = push_to_sparkfun(to_post)
#     logging.info(push.url)
#     get_all_data_from_sparkfun()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARN)
    while True:
        to_post = get_current_data_from_ford()
        push = push_to_sparkfun(to_post)
        data = get_all_data_from_sparkfun()
        save_to_s3(filename,data)
        time.sleep(60*60)
