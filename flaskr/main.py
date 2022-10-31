from base64 import encodebytes
import io, os
from math import cos, asin, sqrt
import sys
from PIL import Image
import cv2
from fogifier import process_image
from flask import Flask, jsonify, redirect, request, make_response, render_template
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
from geopy.geocoders import GoogleV3
load_dotenv()
import requests

if (not os.path.exists(os.path.join(os.getenv('FLASKR_ROOT'), 'uploaded_images'))):
    os.mkdir(os.path.join(os.getenv('FLASKR_ROOT'), 'uploaded_images'))

app = Flask(__name__, instance_relative_config=True, static_folder='./static', template_folder='./static')
# app = Flask(__name__, instance_relative_config=True)

cors = CORS(app)

app.config['CORS_HEADERS'] = 'Content-Type'
app.config['UPLOAD_FOLDER'] = os.path.join(os.getenv('FLASKR_ROOT'), 'uploaded_images')

app.config.from_mapping(
    SECRET_KEY='dev',
    DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
)

@app.route('/', methods=['GET'])
@cross_origin()
def hello():
    # return redirect('http://localhost:4200/')
    return render_template('index.html')
    
# render website page with image
@app.route('/image/<image_name>')
def load_image(image_name):
    # return redirect('http://localhost:4200/')
    return render_template('index.html')

@app.route('/', methods=['POST'])
def get_data():
    uploaded_file = request.files['file']

    uploaded_file.save(os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename))
    uploaded_file.close()

    latitude = request.form['lat']
    longitude = request.form['lon']

    location_aqi = latlon2aqi(latitude, longitude)
    location_place = latlon2address(latitude, longitude)

    if location_aqi == -1:
        response = make_response("I'm a teapot", 418)
        response.mimetype = "text/plain"
        return response

    processed_image = process_image((os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)), location_place, location_aqi)
    processed_image.save(os.path.join(app.config['UPLOAD_FOLDER'], 'filtered_' + uploaded_file.filename))
    # cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], 'filtered_' + uploaded_file.filename), processed_image)

    original_image = process_image((os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)), location_place, location_aqi, True)
    original_image.save(os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename))

    response = make_response("Success!", 200)
    response.mimetype = "text/plain"

    return response

def get_response_image(image_path):
    with Image.open(image_path, mode='r') as im:
        pil_img = im.convert('RGB')
        byte_arr = io.BytesIO()
        pil_img.save(byte_arr, format='JPEG')
        encoded_img = encodebytes(byte_arr.getvalue()).decode('ascii')
    return encoded_img

# send image back to fontend
@app.route('/send_image/<image_name>')
def send_image(image_name):
    encoded_imges = []

    try:
        result = [os.path.join(app.config['UPLOAD_FOLDER'], 'filtered_' + image_name), os.path.join(app.config['UPLOAD_FOLDER'], image_name)]

        for image_path in result:
            encoded_imges.append(get_response_image(image_path))

        image_path = ''

        # delete images from local storage
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], 'filtered_' + image_name))
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image_name))
    except Exception:
        print (sys.exc_info())
        result = None
        
    return jsonify({'result': encoded_imges})


def latlon2address(lat, lon):
    geolocator = GoogleV3(api_key=os.getenv('GEOLOCATOR_API_KEY'))
    locations = geolocator.reverse("{}, {}".format(lat, lon), exactly_one=True)

    if locations:
        locations_list = locations.raw['address_components']

        # filter locations_list and find locality type
        for location in locations_list:
            if 'locality' in location['types']:
                # print (location['long_name'])
                return location['long_name']

def latlon2city(lat, lon):
    aqi_api_url = "https://api.waqi.info/feed/geo:{};{}/?token={}".format(lat, lon, os.getenv('AIR_POLLUTION_TOKEN'))
    air_pollution_data = requests.get(aqi_api_url).json()

    # print ("Adresa: " + air_pollution_data)

    location_place = air_pollution_data['data']['city']['name']
    return location_place


def latlon2aqi(lat, lon):
    aqi_api_url = "https://data.sensor.community/airrohr/v1/filter/area={},{},10".format(lat, lon)
    response = requests.get(aqi_api_url).json()
    if len(response) == 0:
        return -1
    data = sensor_data_to_loc_aqi(filter_non_air_sensors(response))
    if len(data) == 0:
        return -1
    closest_sensor = sort_closest_data(lat, lon, data)[0]
    # print ('Adresa senzora jeeeee ' + latlon2address(closest_sensor[0], closest_sensor[1]))
    return max(closest_sensor[2], closest_sensor[3])


def calc_aqi(sensor):
    p1 = sensor['sensordatavalues'][0]['value'] if sensor['sensordatavalues'][0]['value_type'] == 'P1' else \
    sensor['sensordatavalues'][1]['value']
    p2 = sensor['sensordatavalues'][0]['value'] if sensor['sensordatavalues'][0]['value_type'] == 'P2' else \
    sensor['sensordatavalues'][1]['value']
    p1 = float(p1)
    p2 = float(p2)

    def get_p2_formula_data(conc):
        conc = int(conc)
        if 0 < conc <= 12:
            return 0, 12, 0, 50
        elif 12 < conc <= 35.5:
            return 12, 35.5, 51, 100
        elif 35.5 < conc <= 55.5:
            return 35.5, 55.5, 101, 150
        elif 55.5 < conc <= 150.5:
            return 55.5, 150.5, 151, 200
        elif 150.5 < conc <= 250.5:
            return 150.5, 250.5, 201, 300
        elif 250.5 < conc <= 500.5:
            return 250.5, 500.5, 301, 500
        else:
            # hazardous, aqi is not applicable
            return 500, 1000, 500, 1000

    def get_p1_formula_data(conc):
        if 0 < conc <= 55:
            return 0, 55, 0, 50
        elif 55 < conc <= 155:
            return 55, 155, 51, 100
        elif 155 < conc <= 255:
            return 155, 255, 101, 150
        elif 255 < conc <= 355:
            return 255, 355, 151, 200
        elif 355 < conc <= 425:
            return 355, 425, 201, 300
        elif 425 < conc <= 600:
            return 425, 600, 301, 500
        else:
            # hazardous, aqi is not applicable
            return 600, 1000, 500, 1000

    def formula(conc, conc_l, conc_h, aqi_l, aqi_h):
        return int(((aqi_h - aqi_l) / (conc_h - conc_l)) * (conc - conc_l) + aqi_l)

    return formula(p1, *get_p1_formula_data(p1)), formula(p2, *get_p2_formula_data(p2))


def closest(data, v):
    return min(data, key=lambda p: distance(v['lat'], v['lon'], float(p['location']['latitude']), float(p['location']['longitude'])))


def filter_non_air_sensors(data):
    aux = [x if any('P1' == y['value_type'] or 'P2' == y['value_type'] for y in x['sensordatavalues']) else None for x in data]
    return list(filter(lambda x: x is not None, aux))


def sensor_data_to_loc_aqi(data):
    return list(
        map(lambda x: (float(x['location']['latitude']), float(x['location']['longitude']), *calc_aqi(x)), data))


def sort_closest_data(lat, lon, data):
    data = sorted(data, key=lambda x: distance(lat, lon, x[0], x[1]))
    return data


def distance(lat1, lon1, lat2, lon2):
    p = 0.017453292519943295

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    hav = 0.5 - cos((lat2-lat1)*p)/2 + cos(lat1*p)*cos(lat2*p) * (1-cos((lon2-lon1)*p)) / 2
    return 12742 * asin(sqrt(hav))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)