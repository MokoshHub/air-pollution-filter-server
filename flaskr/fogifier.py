import os
import random
from datetime import datetime
import cv2 as cv
from math import log
from skimage import io
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageFilter
import numpy as np
from dotenv import load_dotenv

load_dotenv()

COLORS_HEX = {
    "good": "#3ebd11",
    "mild": "#e3dc33",
    "unhealthy_sens": "#e08111",
    "unhealthy": "#d10000",
    "unhealthy_very": "#761586",
    "hazard": "#4e0000",
}

COLORS = {
    "good": (62, 189, 17),
    "mild": (227, 220, 51),
    "unhealthy_sens": (224, 129, 17),
    "unhealthy": (209, 0, 0),
    "unhealthy_very": (118, 21, 134),
    "hazard": (0, 0, 78),
}


def load_image(image_path):

    # Preprocessing might happen here, that's why it's not inline
    loaded_image = cv.cvtColor(io.imread(image_path), cv.COLOR_BGR2RGB)

    return loaded_image


def calculate_pollution_rating(pollution_level):

    pollution_rating = ""

    if int(pollution_level) < 51:
        pollution_rating = "good"
    elif int(pollution_level) < 101:
        pollution_rating = "mild"
    elif int(pollution_level) < 151:
        pollution_rating = "unhealthy_sens"
    elif int(pollution_level) < 201:
        pollution_rating = "unhealthy"
    elif int(pollution_level) < 301:
        pollution_rating = "unhealthy_very"
    else:
        pollution_rating = "hazard"

    return pollution_rating


def fogify_image(image, pollution_level=100, fog_image="none", fog_opacity=0.5):

    # TODO: Figure out proper transformations from pollution_level to
    # alpha and beta params for convertScaleAbs, below are placeholder
    # Recommended values for alpha are [1.0-3.0]
    # Recommended values for beta are [0-100]
    alpha = int(pollution_level) / 100
    beta = int(pollution_level) - 100

    fogified_image = cv.convertScaleAbs(image, alpha=alpha, beta=beta)

    if fog_image != "none":

        fog = cv.cvtColor(io.imread(fog_image), cv.COLOR_BGR2RGB)
        fog = cv.resize(
            fog, (image.shape[1], image.shape[0]), interpolation=cv.INTER_NEAREST
        )
        fogified_image = cv.addWeighted(image, fog_opacity, fog, (1 - fog_opacity), 0)

    return fogified_image


def create_rounded_rectangle_mask(rectangle, radius):

    # SOURCE: https://stackoverflow.com/questions/50433000/blur-a-region-shaped-like-a-rounded-rectangle-inside-an-image
    # create mask image. all pixels set to translucent
    solid_fill = (50, 50, 50, 255)
    mask = Image.new("RGBA", rectangle.size, (0, 0, 0, 0))

    # create corner
    corner = Image.new("RGBA", (radius, radius), (0, 0, 0, 0))
    draw = ImageDraw.Draw(corner)
    # added the fill = .. you only drew a line, no fill
    draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=solid_fill)

    # max_x, max_y
    mx, my = rectangle.size

    # paste corner rotated as needed
    # use corners alpha channel as mask

    mask.paste(corner, (0, 0), corner)
    mask.paste(corner.rotate(90), (0, my - radius), corner.rotate(90))
    mask.paste(corner.rotate(180), (mx - radius, my - radius), corner.rotate(180))
    mask.paste(corner.rotate(270), (mx - radius, 0), corner.rotate(270))

    # draw both inner rects
    draw = ImageDraw.Draw(mask)
    draw.rectangle([(radius, 0), (mx - radius, my)], fill=solid_fill)
    draw.rectangle([(0, radius), (mx, my - radius)], fill=solid_fill)

    return mask


def add_frame_and_tab(image, pollution_level=100):

    # Adds frame and tab depending on color from COLORS
    image = Image.fromarray(image)
    fill_color = tuple(reversed(COLORS[calculate_pollution_rating(pollution_level)]))
    # fill_color = COLORS[calculate_pollution_rating(pollution_level)]

    blur_intensity = 5

    image_with_borders = ImageOps.expand(image, border=(5, 5), fill=fill_color)
    height_factor = max(
        0.775, 1 - (image_with_borders.height / image_with_borders.width)
    )
    # print(1 - (image_with_borders.height / image_with_borders.width))
    # print(height_factor)

    draw = ImageDraw.Draw(image_with_borders, "RGBA")

    if image_with_borders.width < image_with_borders.height:
        tab_coords = {
            "left": image_with_borders.width * 0.2
            - (1 if int(image_with_borders.width * 0.2) % 2 == 1 else 0),
            "right": image_with_borders.width * 0.8
            + (1 if int(image_with_borders.width * 0.8) % 2 == 1 else 0),
            "bottom": image_with_borders.height,
            "top": image_with_borders.height,  # this is to be edited in specific tabs
        }
    else:
        tab_coords = {
            "left": image_with_borders.width * 0.35
            - (1 if int(image_with_borders.width * 0.2) % 2 == 1 else 0),
            "right": image_with_borders.width * 0.65
            + (1 if int(image_with_borders.width * 0.8) % 2 == 1 else 0),
            "bottom": image_with_borders.height,
            "top": image_with_borders.height,  # this is to be edited in specific tabs
        }

    cropped_img = image_with_borders.crop(
        (
            tab_coords["left"],
            tab_coords["top"] * height_factor,
            tab_coords["right"],
            tab_coords["bottom"],
        )
    )

    # # the filter removes the alpha, you need to add it again by converting to RGBA
    blurred_img = cropped_img.filter(ImageFilter.GaussianBlur(blur_intensity)).convert(
        "RGBA"
    )

    # # paste blurred, uses alphachannel of create_rounded_rectangle_mask() as mask
    # # only those parts of the mask that have a non-zero alpha gets pasted
    image_with_borders.paste(
        blurred_img,
        (int(tab_coords["left"]), int(tab_coords["top"] * height_factor)),
        create_rounded_rectangle_mask(cropped_img, radius=10),
    )

    draw.rounded_rectangle(
        (
            tab_coords["left"],
            tab_coords["top"] * height_factor,
            tab_coords["right"],
            tab_coords["bottom"],
        ),
        radius=10,
        fill=(0, 0, 0, 127),
    )

    draw.rounded_rectangle(
        (
            tab_coords["left"],
            tab_coords["top"] * 0.9,
            tab_coords["right"],
            tab_coords["bottom"],
        ),
        radius=10,
        fill=(*fill_color, 127),
    )

    draw.rounded_rectangle(
        (
            tab_coords["left"],
            tab_coords["top"] * 0.95,
            tab_coords["right"],
            tab_coords["bottom"],
        ),
        radius=10,
        fill=fill_color,
    )

    image_with_borders = cv.cvtColor(np.asarray(image_with_borders), cv.COLOR_RGBA2BGR)
    return image_with_borders


def find_font_size(text, text_size_goal, image_size, typeface, debug=False):

    target_font_size = 1  # Starting font size for text fitting
    text_type = ImageFont.truetype(typeface, target_font_size)
    while text_type.getsize(text)[1] < text_size_goal * image_size:
        # Iterate until the text size is just larger than the criteria
        target_font_size += 1
        if debug:
            print(target_font_size)
        text_type = ImageFont.truetype(typeface, target_font_size)

    # De-increment to ensure it's not larger than goal
    target_font_size -= 1

    return target_font_size


def write_overlay_text(image, location, timestamp, pollution_level, typeface):

    image = Image.fromarray(image)
    draw = ImageDraw.Draw(image)

    aqi_text = "AQI "
    aqi_values_text = str(pollution_level)
    aqi_text_font = ImageFont.truetype(
        typeface, find_font_size(aqi_text, 0.075, image.height, typeface)
    )
    aqi_text_width, aqi_text_height = draw.textsize(aqi_text, font=aqi_text_font)
    aqi_number_text_width, aqi_number_text_height = draw.textsize(
        aqi_values_text, font=aqi_text_font
    )

    draw.text(
        (
            (image.width - aqi_text_width) / 2 - aqi_number_text_width / 2,
            ((image.height - aqi_text_height) * 0.86),
        ),
        aqi_text,
        fill="#ffffff",
        font=aqi_text_font,
    )

    draw.text(
        (
            (image.width - aqi_number_text_width) / 2 + aqi_text_width / 2,
            ((image.height - aqi_text_height) * 0.86),
        ),
        aqi_values_text,
        fill=COLORS[calculate_pollution_rating(pollution_level)],
        font=aqi_text_font,
    )

    draw = ImageDraw.Draw(image)
    location_text = location[:]
    location_text_font = ImageFont.truetype(
        typeface, find_font_size(location_text, 0.035, image.height, typeface)
    )
    text_width, text_height = draw.textsize(location_text, font=location_text_font)
    draw.text(
        ((image.width - text_width) / 2, ((image.height - text_height) * 0.93625)),
        location_text,
        fill="#ffffff",
        font=location_text_font,
    )

    timestamp_text_font = location_text_font
    text_width, text_height = draw.textsize(timestamp, font=timestamp_text_font)
    draw.text(
        ((image.width - text_width) / 2, ((image.height - text_height) * 0.99)),
        timestamp,
        fill="#ffffff",
        font=timestamp_text_font,
    )

    image = np.array(image)

    return image


def process_image(
    image_path, location, pollution_level, timestamp, original=False, debug=False
):

    # timestamp = datetime.now()
    # timestamp = timestamp.strftime("%d/%m %H:%M")

    # This is the "main" method

    if original:
        raw_image = load_image(image_path)
        framed_image = add_frame_and_tab(raw_image, pollution_level)
        texted_image = write_overlay_text(
            framed_image,
            location.upper(),
            timestamp,
            pollution_level,
            os.path.join(
                os.getenv("FLASKR_ROOT"), "static", "assets", "Roboto-Light.ttf"
            ),
        )
        final_image = texted_image

    else:

        # Avoiding division by 0 here:
        pollution_level = 1 if (pollution_level == 0) else pollution_level

        # Method picks a random fog overlay image and runs a calculation
        # to modify the blend opacity of fog to main photo
        fog_overlay_img = random.choice(
            os.listdir(os.path.join(os.getenv("FLASKR_ROOT"), "Fogs"))
        )
        fog_opacity = (
            1
            if (log(1 / (pollution_level / 100) + 1) > 1)
            else log(1 / (pollution_level / 100) + 1)
        )

        raw_image = load_image(image_path)
        fogified_image = fogify_image(
            raw_image,
            pollution_level,
            os.path.join(os.getenv("FLASKR_ROOT"), "Fogs", fog_overlay_img),
            fog_opacity,
        )
        framed_image = add_frame_and_tab(fogified_image, pollution_level)
        texted_image = write_overlay_text(
            framed_image,
            location.upper(),
            timestamp,
            pollution_level,
            os.path.join(
                os.getenv("FLASKR_ROOT"), "static", "assets", "Roboto-Light.ttf"
            ),
        )
        final_image = texted_image

    if debug:
        # OpenCV image display here
        cv.imshow("Final image", final_image)
        cv.waitKey(0)
        cv.destroyAllWindows()

        # PIL image display here
        # debug_image = cv.cvtColor(final_image, cv.COLOR_BGR2RGB)
        # debug_image = Image.fromarray(debug_image)
        # debug_image.show()

    # final_image = cv.cvtColor(final_image, cv.COLOR_BGR2RGB)
    final_image = Image.fromarray(final_image)
    return final_image


# process_image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/New-York-Jan2005.jpg/1280px-New-York-Jan2005.jpg",
#               "NYC",
#               500,
#               False,
#               True)
